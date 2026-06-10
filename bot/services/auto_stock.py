import asyncio
import csv
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import AutoStockSource
from bot.database.session import SessionLocal
from bot.services.products import add_stock_batch, unsold_stock_count

DEFAULT_TARGET_STOCK = 40000
DEFAULT_REFILL_THRESHOLD = 20000
DEFAULT_REFILL_CHECK_SECONDS = 300
DOWNLOAD_TIMEOUT_SECONDS = 900
INSERT_BATCH_SIZE = 1000


@dataclass(frozen=True)
class RefillResult:
    source_id: int
    product_id: int
    current_stock: int
    added_count: int
    next_line_number: int
    target_stock: int
    refill_threshold: int
    message: str


def normalize_stock_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if "dropbox.com" not in parts.netloc:
        return url.strip()
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["dl"] = "1"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def stock_line_from_text(raw_line: str) -> str | None:
    line = raw_line.strip().strip("\ufeff")
    if not line:
        return None
    if "\t" in line:
        cells = [cell.strip() for cell in line.split("\t") if cell.strip()]
        lowered = {cell.lower() for cell in cells}
        if {"no", "email/username", "password", "full account"} & lowered:
            return None
        if cells and cells[0].isdigit() and len(cells) >= 4 and "@" in cells[-1]:
            return cells[-1]
        if len(cells) >= 2:
            return "|".join(cells)
    if "," in line and "|" not in line:
        try:
            row = next(csv.reader([line]))
        except csv.Error:
            row = []
        cells = [str(cell).strip() for cell in row if str(cell).strip()]
        lowered = {cell.lower() for cell in cells}
        if {"no", "email/username", "password", "full account"} & lowered:
            return None
        if cells and cells[0].isdigit() and len(cells) >= 4 and "@" in cells[-1]:
            return cells[-1]
        if len(cells) >= 2:
            return "|".join(cells)
    return line


async def upsert_auto_stock_source(
    session: AsyncSession,
    product_id: int,
    url: str,
    target_stock: int = DEFAULT_TARGET_STOCK,
    refill_threshold: int = DEFAULT_REFILL_THRESHOLD,
) -> AutoStockSource:
    target_stock = max(int(target_stock), 1)
    refill_threshold = max(min(int(refill_threshold), target_stock - 1), 0)
    source = await session.scalar(select(AutoStockSource).where(AutoStockSource.product_id == product_id))
    if source:
        source.url = normalize_stock_url(url)
        source.target_stock = target_stock
        source.refill_threshold = refill_threshold
        source.is_active = True
        source.last_error = None
    else:
        source = AutoStockSource(
            product_id=product_id,
            url=normalize_stock_url(url),
            target_stock=target_stock,
            refill_threshold=refill_threshold,
        )
        session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


async def get_auto_stock_source(session: AsyncSession, product_id: int) -> AutoStockSource | None:
    return await session.scalar(select(AutoStockSource).where(AutoStockSource.product_id == product_id))


async def list_active_auto_stock_sources(session: AsyncSession) -> list[AutoStockSource]:
    result = await session.execute(select(AutoStockSource).where(AutoStockSource.is_active.is_(True)).order_by(AutoStockSource.id))
    return list(result.scalars().all())


async def stop_auto_stock_source(session: AsyncSession, product_id: int) -> bool:
    source = await session.scalar(select(AutoStockSource).where(AutoStockSource.product_id == product_id))
    if not source:
        return False
    source.is_active = False
    await session.commit()
    return True


async def reset_auto_stock_progress(session: AsyncSession, product_id: int) -> bool:
    source = await session.scalar(select(AutoStockSource).where(AutoStockSource.product_id == product_id))
    if not source:
        return False
    source.next_line_number = 0
    source.last_added_count = 0
    source.last_error = None
    source.is_active = True
    await session.commit()
    return True


async def _download_needed_lines(source: AutoStockSource, needed_count: int) -> tuple[list[str], int, bool]:
    lines: list[str] = []
    seen_line_number = 0
    timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as http_session:
        async with http_session.get(normalize_stock_url(source.url), allow_redirects=True) as response:
            response.raise_for_status()
            remainder = ""
            async for chunk in response.content.iter_chunked(64 * 1024):
                text = chunk.decode("utf-8", errors="ignore")
                parts = (remainder + text).splitlines()
                if text and not text.endswith(("\n", "\r")):
                    remainder = parts.pop() if parts else ""
                else:
                    remainder = ""
                for raw_line in parts:
                    if seen_line_number < source.next_line_number:
                        seen_line_number += 1
                        continue
                    line = stock_line_from_text(raw_line)
                    seen_line_number += 1
                    if line:
                        lines.append(line)
                    if len(lines) >= needed_count:
                        return lines, seen_line_number, False
            if remainder:
                if seen_line_number >= source.next_line_number:
                    line = stock_line_from_text(remainder)
                    if line:
                        lines.append(line)
                seen_line_number += 1
    return lines, seen_line_number, True


async def refill_source(session: AsyncSession, source_id: int) -> RefillResult:
    source = await session.scalar(select(AutoStockSource).where(AutoStockSource.id == source_id))
    if not source:
        raise ValueError("Auto stock source not found.")
    if not source.is_active:
        current = await unsold_stock_count(session, source.product_id)
        return RefillResult(source.id, source.product_id, current, 0, source.next_line_number, source.target_stock, source.refill_threshold, "Auto refill is stopped.")

    current_stock = await unsold_stock_count(session, source.product_id)
    if current_stock > source.refill_threshold:
        return RefillResult(
            source.id,
            source.product_id,
            current_stock,
            0,
            source.next_line_number,
            source.target_stock,
            source.refill_threshold,
            "Stock is still above threshold.",
        )

    needed_count = max(source.target_stock - current_stock, 0)
    if needed_count <= 0:
        return RefillResult(source.id, source.product_id, current_stock, 0, source.next_line_number, source.target_stock, source.refill_threshold, "No refill needed.")

    try:
        lines, next_line_number, exhausted = await _download_needed_lines(source, needed_count)
        added_count = 0
        for index in range(0, len(lines), INSERT_BATCH_SIZE):
            added_count += await add_stock_batch(session, source.product_id, lines[index : index + INSERT_BATCH_SIZE])
        source.next_line_number = next_line_number
        source.last_added_count = added_count
        source.last_run_at = datetime.utcnow()
        source.last_error = None
        if exhausted and added_count == 0:
            source.is_active = False
            source.last_error = "No new stock lines found. Source file may be finished."
        await session.commit()
    except Exception as exc:
        await session.rollback()
        source = await session.scalar(select(AutoStockSource).where(AutoStockSource.id == source_id))
        if source:
            source.last_error = str(exc)[:2000]
            source.last_run_at = datetime.utcnow()
            await session.commit()
        raise

    new_stock = current_stock + added_count
    return RefillResult(
        source.id,
        source.product_id,
        new_stock,
        added_count,
        source.next_line_number,
        source.target_stock,
        source.refill_threshold,
        "Refill completed." if added_count else "No new stock was added.",
    )


async def run_auto_stock_once() -> list[RefillResult]:
    results: list[RefillResult] = []
    async with SessionLocal() as session:
        sources = await list_active_auto_stock_sources(session)
    for source in sources:
        async with SessionLocal() as session:
            results.append(await refill_source(session, source.id))
    return results


async def auto_stock_worker(admin_ids: Iterable[int], notify) -> None:
    await asyncio.sleep(20)
    while True:
        try:
            results = await run_auto_stock_once()
            for result in results:
                if result.added_count > 0:
                    text = (
                        "Auto Stock Refilled\n\n"
                        f"Product ID: #{result.product_id}\n"
                        f"Added: {result.added_count}\n"
                        f"Current Stock: {result.current_stock}\n"
                        f"Next Line: {result.next_line_number}"
                    )
                    for admin_id in admin_ids:
                        await notify(admin_id, text)
        except Exception as exc:
            for admin_id in admin_ids:
                await notify(admin_id, f"Auto Stock Error\n\n{exc}")
        await asyncio.sleep(DEFAULT_REFILL_CHECK_SECONDS)
