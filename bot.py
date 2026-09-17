import logging
import re
from datetime import datetime, timedelta, timezone

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
    PreCheckoutQueryHandler
)

from config import TELEGRAM_BOT_TOKEN

from product_extractor import extract_product
from shopping_search import search_products
from matcher import filter_and_sort_products

from database import (
    initialize_database,
    add_user,
    get_user,
    can_search,
    record_search,
    is_premium,
    set_premium,
    add_referral,
    get_referral_info,
    mark_referral_reward_given
)


# ==========================================
# SETTINGS
# ==========================================

FREE_SEARCH_LIMIT = 3

REFERRALS_REQUIRED = 10

FREE_PREMIUM_DAYS = 30

# Premium price in Telegram Stars
PREMIUM_PRICE_STARS = 100

# Telegram requires 30 days for bot subscriptions
SUBSCRIPTION_PERIOD = 2592000

PREMIUM_PAYLOAD = "shopping_friend_premium_monthly"


# ==========================================
# LOGGING
# ==========================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


# ==========================================
# PRICE CLEANING
# ==========================================

def clean_price(price):

    if not price:
        return None

    numbers = re.findall(
        r"[\d,]+(?:\.\d+)?",
        str(price)
    )

    if not numbers:
        return None

    return numbers[0]


# ==========================================
# FORMAT SHOPPING RESULTS
# ==========================================

def format_results(product, results):

    text = (
        "🔍 <b>Product Found</b>\n\n"
        f"<b>{product['title'][:300]}</b>\n\n"
        "💰 <b>Price Comparison</b>\n\n"
    )

    for index, item in enumerate(
        results[:8],
        start=1
    ):

        price = clean_price(
            item.get("price")
        )

        source = (
            item.get("source")
            or "Unknown store"
        )

        title = item.get(
            "title",
            "Product"
        )

        match_score = item.get(
            "match_score",
            0
        )

        text += (
            f"<b>{index}. {source}</b>\n"
            f"💵 ₹{price or 'Price unavailable'}\n"
            f"{title[:120]}\n"
            f"Match: {match_score}%\n\n"
        )

    if results:

        cheapest = results[0]

        cheapest_price = clean_price(
            cheapest.get("price")
        )

        if cheapest_price:

            text += (
                f"🏷️ <b>Lowest price found:</b> "
                f"₹{cheapest_price}\n"
            )

    return text


# ==========================================
# /START
# ==========================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    user_id = user.id

    is_new_user = add_user(
        user_id,
        user.username,
        user.first_name
    )

    # ======================================
    # REFERRAL PROCESSING
    # ======================================

    if is_new_user and context.args:

        referral_code = context.args[0]

        try:

            referrer_id = int(
                referral_code
            )

            referral_added, referral_count = add_referral(
                referrer_id,
                user_id
            )

            if referral_added:

                referral_count, rewards_given = get_referral_info(
                    referrer_id
                )

                available_rewards = (
                    referral_count // REFERRALS_REQUIRED
                )

                if available_rewards > rewards_given:

                    now = datetime.now(
                        timezone.utc
                    )

                    referrer = get_user(
                        referrer_id
                    )

                    premium_until = (
                        now
                        + timedelta(
                            days=FREE_PREMIUM_DAYS
                        )
                    )

                    if referrer and referrer[4]:

                        try:

                            existing_expiry = datetime.fromisoformat(
                                referrer[4]
                            )

                            if existing_expiry > now:

                                premium_until = (
                                    existing_expiry
                                    + timedelta(
                                        days=FREE_PREMIUM_DAYS
                                    )
                                )

                        except Exception:

                            pass

                    set_premium(
                        referrer_id,
                        premium_until.isoformat()
                    )

                    mark_referral_reward_given(
                        referrer_id
                    )

                    try:

                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=(
                                "🎉 <b>Referral Reward Unlocked!</b>\n\n"
                                f"You reached "
                                f"<b>{referral_count} successful referrals</b>.\n\n"
                                "⭐ You received "
                                "<b>1 month FREE Premium!</b>"
                            ),
                            parse_mode="HTML"
                        )

                    except Exception as e:

                        print(
                            "Could not notify referrer:",
                            e
                        )

        except ValueError:

            pass

    # ======================================
    # START MESSAGE
    # ======================================

    await update.message.reply_text(
        "🛒 <b>Shopping Friend</b>\n\n"
        "Send me a product URL and I'll search "
        "for available prices.\n\n"
        f"🎁 Free users get "
        f"<b>{FREE_SEARCH_LIMIT} searches per day</b>.\n\n"
        "🎁 Refer <b>10 new users</b> and get "
        "<b>1 month FREE Premium</b>.\n\n"
        "⭐ Use /premium for Premium.\n"
        "👥 Use /referral for your referral link.",
        parse_mode="HTML"
    )


# ==========================================
# /REFERRAL
# ==========================================

async def referral(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    add_user(
        user.id,
        user.username,
        user.first_name
    )

    referral_count, rewards_given = get_referral_info(
        user.id
    )

    bot = await context.bot.get_me()

    referral_link = (
        f"https://t.me/{bot.username}?start={user.id}"
    )

    if referral_count == 0:
        remaining = REFERRALS_REQUIRED
    else:
        remaining = REFERRALS_REQUIRED - (
            referral_count % REFERRALS_REQUIRED
        )

        if remaining == 0:
            remaining = REFERRALS_REQUIRED

    await update.message.reply_text(
        "🎁 <b>Referral Program</b>\n\n"
        f"👥 Successful referrals: "
        f"<b>{referral_count}</b>\n\n"
        f"🎯 Referrals until next reward: "
        f"<b>{remaining}</b>\n\n"
        "⭐ Every 10 successful referrals = "
        "<b>1 month FREE Premium</b>\n\n"
        "🔗 <b>Your referral link:</b>\n\n"
        f"<code>{referral_link}</code>\n\n"
        "Share this link with your friends!",
        parse_mode="HTML"
    )


# ==========================================
# /PREMIUM
# ==========================================

async def premium(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    add_user(
        user.id,
        user.username,
        user.first_name
    )

    if is_premium(user.id):

        await update.message.reply_text(
            "⭐ <b>You are already Premium!</b>\n\n"
            "You currently have access to Premium features.",
            parse_mode="HTML"
        )

        return

    keyboard = [
        [
            InlineKeyboardButton(
                f"⭐ Get Premium — {PREMIUM_PRICE_STARS} Stars/month",
                callback_data="buy_premium"
            )
        ]
    ]

    reply_markup = InlineKeyboardMarkup(
        keyboard
    )

    await update.message.reply_text(
        "⭐ <b>Shopping Friend Premium</b>\n\n"
        "Premium includes:\n\n"
        "🚫 No advertisements\n"
        "🔎 More comparison searches\n"
        "📊 Price history\n"
        "🔔 Price-drop alerts\n"
        "🎯 Advanced features\n\n"
        f"💳 Price: <b>{PREMIUM_PRICE_STARS} Stars/month</b>\n\n"
        "🎁 Or refer 10 new users to get "
        "1 month FREE Premium.",
        parse_mode="HTML",
        reply_markup=reply_markup
    )


# ==========================================
# BUY PREMIUM BUTTON
# ==========================================

async def buy_premium(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    try:
        prices = [
            LabeledPrice(
                "Shopping Friend Premium",
                PREMIUM_PRICE_STARS
            )
        ]

        # Telegram Stars subscriptions are created through
        # create_invoice_link(). The subscription period is not
        # accepted by send_invoice() in python-telegram-bot 22.8.
        invoice_link = await context.bot.create_invoice_link(
            title="Shopping Friend Premium",
            description=(
                "Premium subscription for Shopping Friend. "
                "Includes an ad-free experience and Premium features."
            ),
            payload=PREMIUM_PAYLOAD,
            currency="XTR",
            prices=prices,
            subscription_period=SUBSCRIPTION_PERIOD
        )

        payment_keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f"⭐ Pay {PREMIUM_PRICE_STARS} Stars",
                        url=invoice_link
                    )
                ]
            ]
        )

        await query.message.reply_text(
            "⭐ <b>Shopping Friend Premium</b>\n\n"
            f"💳 Price: <b>{PREMIUM_PRICE_STARS} Stars/month</b>\n\n"
            "Click the button below to open the Telegram Stars "
            "payment screen.",
            parse_mode="HTML",
            reply_markup=payment_keyboard
        )

    except Exception as e:
        logging.exception("Could not create Premium invoice")

        await query.message.reply_text(
            "❌ I couldn't create the Premium payment link right now.\n\n"
            "Please try again in a moment."
        )


# ==========================================
# PRE-CHECKOUT
# ==========================================

async def pre_checkout(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.pre_checkout_query

    if query.invoice_payload != PREMIUM_PAYLOAD:

        await query.answer(
            ok=False,
            error_message="Invalid Premium payment."
        )

        return

    if query.currency != "XTR":

        await query.answer(
            ok=False,
            error_message="Invalid payment currency."
        )

        return

    if query.total_amount != PREMIUM_PRICE_STARS:

        await query.answer(
            ok=False,
            error_message="Invalid Premium price."
        )

        return

    await query.answer(
        ok=True
    )


# ==========================================
# SUCCESSFUL PAYMENT
# ==========================================

async def successful_payment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    payment = update.message.successful_payment

    if payment.invoice_payload != PREMIUM_PAYLOAD:

        return

    user = update.effective_user

    # Telegram supplies the subscription expiration
    # for recurring subscription payments.
    expiration_timestamp = (
        payment.subscription_expiration_date
    )

    if expiration_timestamp:

        premium_until = datetime.fromtimestamp(
            expiration_timestamp,
            tz=timezone.utc
        )

    else:

        premium_until = (
            datetime.now(timezone.utc)
            + timedelta(
                days=FREE_PREMIUM_DAYS
            )
        )

    set_premium(
        user.id,
        premium_until.isoformat()
    )

    charge_id = payment.telegram_payment_charge_id

    logging.info(
        "Premium payment received: user=%s charge=%s",
        user.id,
        charge_id
    )

    await update.message.reply_text(
        "🎉 <b>Premium Activated!</b>\n\n"
        "⭐ Your Shopping Friend Premium is now active.\n\n"
        "🚫 No advertisements\n"
        "🔎 Premium search access\n"
        "📊 Premium features\n\n"
        f"Premium active until:\n"
        f"<b>{premium_until.strftime('%d %B %Y')}</b>\n\n"
        "Thank you for supporting Shopping Friend! ❤️",
        parse_mode="HTML"
    )


# ==========================================
# /HELP
# ==========================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "📖 <b>How to use Shopping Friend</b>\n\n"
        "1️⃣ Send a product URL.\n"
        "2️⃣ I'll identify the product.\n"
        "3️⃣ I'll search shopping results.\n"
        "4️⃣ I'll compare prices.\n\n"
        "<b>Commands</b>\n\n"
        "/start - Start the bot\n"
        "/premium - Premium subscription\n"
        "/referral - Referral program\n"
        "/help - Help",
        parse_mode="HTML"
    )


# ==========================================
# HANDLE PRODUCT URL
# ==========================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.message

    if not message or not message.text:

        return

    user = update.effective_user

    add_user(
        user.id,
        user.username,
        user.first_name
    )

    # ======================================
    # SEARCH LIMIT
    # ======================================

    if not can_search(
        user.id,
        FREE_SEARCH_LIMIT
    ):

        await message.reply_text(
            "🚫 <b>Daily search limit reached</b>\n\n"
            f"Free users can make "
            f"<b>{FREE_SEARCH_LIMIT} searches per day</b>.\n\n"
            "⭐ Get Premium for more searches "
            "and an ad-free experience.\n\n"
            "🎁 Or refer 10 new users to get "
            "1 month FREE Premium.",
            parse_mode="HTML"
        )

        return

    # ======================================
    # URL CHECK
    # ======================================

    url = message.text.strip()

    if not (
        url.startswith("http://")
        or url.startswith("https://")
    ):

        await message.reply_text(
            "❌ Please send a valid product URL."
        )

        return

    processing_message = await message.reply_text(
        "🔍 Analyzing the product...\n"
        "Please wait."
    )

    # ======================================
    # PRODUCT EXTRACTION
    # ======================================

    product = await extract_product(
        url
    )

    title = product.get(
        "title",
        ""
    ).strip()

    if not title:

        await processing_message.edit_text(
            "❌ I couldn't identify the product.\n\n"
            "Please try another product URL."
        )

        return

    record_search(
        user.id
    )

    await processing_message.edit_text(
        "🔎 <b>Product identified:</b>\n\n"
        f"{title[:300]}\n\n"
        "🛒 Searching shopping results...",
        parse_mode="HTML"
    )

    # ======================================
    # SEARCH
    # ======================================

    results = await search_products(
        title
    )

    if not results:

        await processing_message.edit_text(
            "❌ I couldn't find shopping results "
            "for this product right now."
        )

        return

    # ======================================
    # MATCH
    # ======================================

    matched = filter_and_sort_products(
        title,
        results
    )

    if not matched:

        await processing_message.edit_text(
            "⚠️ I found shopping results, but "
            "couldn't find matching products."
        )

        return

    # ======================================
    # FORMAT
    # ======================================

    text = format_results(
        product,
        matched
    )

    keyboard = []

    for item in matched[:5]:

        link = item.get(
            "link"
        )

        if not link:

            continue

        source = (
            item.get("source")
            or "View offer"
        )

        keyboard.append(
            [
                InlineKeyboardButton(
                    f"🛒 {source[:25]}",
                    url=link
                )
            ]
        )

    reply_markup = None

    if keyboard:

        reply_markup = InlineKeyboardMarkup(
            keyboard
        )

    await processing_message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )


# ==========================================
# MAIN
# ==========================================

def main():

    initialize_database()

    application = (
        Application
        .builder()
        .token(TELEGRAM_BOT_TOKEN)
        .connect_timeout(60)
        .read_timeout(60)
        .write_timeout(60)
        .pool_timeout(60)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    application.add_handler(
        CommandHandler(
            "premium",
            premium
        )
    )

    application.add_handler(
        CommandHandler(
            "referral",
            referral
        )
    )

    # Premium button
    application.add_handler(
        CallbackQueryHandler(
            buy_premium,
            pattern="^buy_premium$"
        )
    )

    # Payment verification
    application.add_handler(
        PreCheckoutQueryHandler(
            pre_checkout
        )
    )

    # Successful payment
    application.add_handler(
        MessageHandler(
            filters.SUCCESSFUL_PAYMENT,
            successful_payment
        )
    )

    # Product URLs
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print(
        "Price comparison bot is running..."
    )

    application.run_polling()


if __name__ == "__main__":
    main()