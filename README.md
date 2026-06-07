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
ADMIN_IDS=your_telegram_user_id
BINANCE_PAY_ID=...
USDT_TRC20_ADDRESS=...
USDT_BEP20_ADDRESS=...
BKASH_NUMBER=...
NAGAD_NUMBER=...
ROCKET_NUMBER=...
REFERRAL_COMMISSION_PERCENT=10
SUPPORT_USERNAME=your_support
MIN_DEPOSIT=1.0
CURRENCY_SYMBOL=$
```

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
