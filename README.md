# Premium Telegram Mail Shop Bot

Production-ready Telegram marketplace bot for selling email account stock with PostgreSQL and Railway deployment.

## Features

- User registration from `/start`
- User dashboard and balance
- Manual deposit requests with admin approval
- Product catalog
- Automatic stock delivery after purchase
- Order history
- Referral links and commission
- Coupon redemption
- Admin panel
- Product creation
- Bulk stock upload
- Deposit review
- Store stats

## Stack

- Python 3.12+
- aiogram 3
- PostgreSQL
- SQLAlchemy async
- Railway worker deployment

## Local Setup

1. Create a virtual environment.
   ```bash
   python -m venv .venv
   ```

2. Activate it.
   ```bash
   .venv\Scripts\activate
   ```

3. Install dependencies.
   ```bash
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and fill in your values.

5. Run the bot.
   ```bash
   python run.py
   ```

## Railway Setup

1. Create a Railway project.
2. Add a PostgreSQL database.
3. Add the bot service from your GitHub repository.
4. Add all required environment variables.
5. Set `DATABASE_URL` from the Railway PostgreSQL reference.
6. Deploy.
7. Open logs and verify:
   - `PostgreSQL connection ready and tables initialized`
   - `Telegram Mail Shop Bot started`

## Required Environment Variables

```env
BOT_TOKEN=your_bot_token
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/database
DATABASE_PUBLIC_URL=
ADMIN_IDS=your_telegram_user_id
BINANCE_PAY_ID=...
USDT_TRC20_ADDRESS=...
USDT_BEP20_ADDRESS=...
BKASH_NUMBER=...
NAGAD_NUMBER=...
ROCKET_NUMBER=...
REFERRAL_COMMISSION_PERCENT=10
SUPPORT_USERNAME=your_support
MIN_DEPOSIT=100
CURRENCY_SYMBOL=TK
USD_TO_TK_RATE=125
SEMI_AUTO_DEPOSIT_ENABLED=true
SEMI_AUTO_DEPOSIT_MAX_AMOUNT=100
SEMI_AUTO_TRUSTED_USER_MIN_APPROVED_DEPOSITS=1
SEMI_AUTO_DAILY_USER_LIMIT=200
OCR_ENABLED=true
OCR_SPACE_API_KEY=helloworld
OCR_SPACE_API_URL=https://api.ocr.space/parse/image
FORCE_JOIN_ENABLED=true
REQUIRED_CHANNEL_USERNAME=@PremiumXMethod
REQUIRED_CHANNEL_LINK=https://t.me/PremiumXMethod
ZINIPAY_TRX_ENABLED=false
ZINIPAY_API_KEY=
ZINIPAY_TRX_BASE_URL=https://api.zinipay.com/v1/trx
```

On Railway, set `DATABASE_URL` as a reference to your PostgreSQL service. If the bot logs show a hostname error for `postgres.railway.internal`, also set `DATABASE_PUBLIC_URL` from the PostgreSQL service and redeploy.

For force-join, add the bot as an admin/member in your required channel so Telegram can verify whether users joined.

Set `ZINIPAY_TRX_ENABLED=true` and `ZINIPAY_API_KEY` to enable direct bKash/Nagad/Rocket TXID verification through ZiniPay. If verification fails, users can still upload a screenshot for manual admin review.

`SEMI_AUTO_DEPOSIT_ENABLED=true` allows trusted small deposits to be approved automatically. For safer personal bKash/Nagad/Rocket use, the bot only auto-approves when the transaction ID is unique, does not look suspicious, the amount is at or below `SEMI_AUTO_DEPOSIT_MAX_AMOUNT`, the user already has at least `SEMI_AUTO_TRUSTED_USER_MIN_APPROVED_DEPOSITS` approved deposit, and today's approved total stays under `SEMI_AUTO_DAILY_USER_LIMIT`. This does not verify personal wallet payments through an official API, so first deposits and risky requests still go to admin review.

`OCR_ENABLED=true` lets the bot run a semi-auto OCR assistant on deposit screenshots. OCR compares screenshot text against the submitted amount and transaction ID, then sends admins a match/mismatch report. OCR is only a review helper; admins should still verify before approval.

## Admin Usage

- `/admin` opens the admin panel.
- Add products with:
  ```text
  Name | Price | Description
  ```
- Add stock using one account per line:
  ```text
  email1@example.com|password1
  email2@example.com|password2
  ```
- Review pending deposits from the admin panel.

## User Usage

- `/start` opens the main menu.
- Products can be purchased from the catalog.
- Purchased account details are delivered immediately after successful balance deduction.
- Users can deposit, redeem coupons, view orders, and share referral links.
