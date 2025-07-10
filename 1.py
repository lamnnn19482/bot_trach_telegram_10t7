import logging
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
import random
import datetime
import asyncio

logging.basicConfig(level=logging.INFO)

# <editor-fold desc="Cấu hình Bot">
BOT_TOKEN = "7301274609:AAE8DazQq8hbgdxM8bx3235xZjSrIq4K9qQ"

NOTE = (
    "💡 Sao rất nhiều lệnh trade: Nên chia nhỏ lệnh, tránh dồn một cục để bị quét một lần!\n"
    "💡 SL thì giữ nguyên, không cần di chuyển nếu giá chưa chạy 1500 giá."
)
# </editor-fold>

# Workflow 3 tầng đơn giản
# Workflow theo yêu cầu
WORKFLOW = {
    "step_1": {
        "question": "Giá có trên VWAP không?",
        "options": {"1": "step_2", "0": "step_2_below"}
    },
    "step_2": {
        "question": "Mặt cười màu gì?\n0 = Xanh\n1 = Đỏ",
        "options": {"0": "should_trade", "1": "end_no_trade"}
    },
    "should_trade": {
        "question": "✅ Nên vào lệnh!\n\n" + NOTE,
        "options": {"Kết quả giao dịch: Thắng": "reason_win", "Kết quả giao dịch: Thua": "reason_lose"}
    },
    "end_no_trade": {
        "question": (
            "❌ VÀO LÀ MẤT TIỀN NHA MẦY\n" * 6 + NOTE
        ),
        "options": {}
    },
    # Nhánh dưới VWAP
    "step_2_below": {
        "question": "Mặt cười màu gì?\n0 = Xanh\n1 = Đỏ",
        "options": {"1": "should_short", "0": "wait_short"}
    },
    "should_short": {
        "question": "🔴 Nên vào lệnh SHORT!\n\n" + NOTE,
        "options": {"Kết quả giao dịch: Thắng": "reason_win_short", "Kết quả giao dịch: Thua": "reason_lose_short"}
    },
    "wait_short": {
        "question": (
            "❌ Vào là MẤT TIỀN\n" * 6 + NOTE
        ),
        "options": {}
    },
    "reason_win": {
        "question": "Bạn thắng vì lý do gì? (Nhập lý do)",
        "options": {}
    },
    "reason_lose": {
        "question": "Bạn thua vì lý do gì? (Nhập lý do)",
        "options": {}
    },
    "reason_win_short": {
        "question": "Bạn thắng (SHORT) vì lý do gì? (Nhập lý do)",
        "options": {}
    },
    "reason_lose_short": {
        "question": "Bạn thua (SHORT) vì lý do gì? (Nhập lý do)",
        "options": {}
    }
}

user_states = {}

ASK_MINUTE, TRADE_RESULT = range(2)

def so_phut_da_troi_qua(phut_nhap, phut_hien_tai):
    if phut_hien_tai >= phut_nhap:
        return phut_hien_tai - phut_nhap
    else:
        return (60 - phut_nhap) + phut_hien_tai

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not hasattr(update, "effective_user") or update.effective_user is None:
        if hasattr(update, "message") and update.message:
            await update.message.reply_text("Không xác định được người dùng. Gõ /start lại.")
        return
    if not hasattr(update, "message") or not update.message:
        return
    user_id = update.effective_user.id if update.effective_user else None
    user_states.pop(user_id, None)
    keyboard = [
        [KeyboardButton("Vào")],
        [KeyboardButton("Lịch sử giao dịch")],
        [KeyboardButton("Kết quả thắng")],
        [KeyboardButton("Kết quả thua")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Chào mừng! Chọn một chức năng bên dưới:",
        reply_markup=reply_markup
    )

def get_keyboard(options): 
    keys = list(options.keys())
    random.shuffle(keys)
    return [keys]

async def send_question(update, step_id):
    step = WORKFLOW[step_id]
    question = step["question"]
    options = step["options"]
    if hasattr(update, "message") and update.message:
        if options:
            keyboard = get_keyboard(options)
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(question, reply_markup=reply_markup)
        else:
            await update.message.reply_text(question + "\n\nGõ /start để kiểm tra lại")

async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not hasattr(update, "message") or not update.message:
        return
    if not hasattr(update, "effective_user") or update.effective_user is None:
        await update.message.reply_text("Không xác định được người dùng. Gõ /start lại.")
        return
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        return
    user_input = update.message.text.strip() if update.message.text else ""
    current_step = user_states.get(user_id, "step_1")
    if current_step not in WORKFLOW:
        await update.message.reply_text("Gõ /start để bắt đầu")
        return
    step = WORKFLOW[current_step]
    options = step["options"]
    # Nếu là bước nhập lý do, lưu vào file và trả về menu chính
    if current_step in ["reason_win", "reason_lose", "reason_win_short", "reason_lose_short"]:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result = "Thắng" if "win" in current_step else "Thua"
        trade_type = "Long" if "short" not in current_step else "Short"
        reason = user_input
        r_value = "1.67R"
        with open("history.txt", "a", encoding="utf-8") as f:
            f.write(f"{now} | {trade_type} | {result} | {reason} | {r_value}\n")
        keyboard = [
            [KeyboardButton("Vào")],
            [KeyboardButton("Lịch sử giao dịch")],
            [KeyboardButton("Kết quả thắng")],
            [KeyboardButton("Kết quả thua")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Đã lưu lịch sử lệnh! Chọn một chức năng bên dưới:",
            reply_markup=reply_markup
        )
        user_states.pop(user_id, None)
        return
    # Nếu chọn đúng option
    if options and user_input in options:
        next_step = options[user_input]
        # Nếu là bước tín hiệu hợp lệ (should_trade hoặc should_short), hỏi phút và đặt biến trạng thái
        if next_step in ["should_trade", "should_short"]:
            user_states.pop(user_id, None)
            if context.user_data is not None:
                context.user_data['waiting_for_minute'] = True
                context.user_data['countdown_next'] = next_step
            await update.message.reply_text("Nhập phút big trader vào lệnh:")
            return
        user_states[user_id] = next_step
        await send_question(update, next_step)
        return
    # Nếu chọn sai option
    user_states.pop(user_id, None)
    keyboard = [
        [KeyboardButton("Vào")],
        [KeyboardButton("Lịch sử giao dịch")],
        [KeyboardButton("Kết quả thắng")],
        [KeyboardButton("Kết quả thua")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Bạn đã chọn sai! Quay lại menu chính. Chọn một chức năng bên dưới:",
        reply_markup=reply_markup
    )

# --- Countdown từng phút, nút Thắng/Thua liên kết nhập lý do ---

async def send_countdown_minute(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not hasattr(context.job, 'chat_id') or not hasattr(context.job, 'data') or context.job.chat_id is None or context.job.data is None:
        return
    chat_id = context.job.chat_id
    minutes_left = None
    if isinstance(context.job.data, dict):
        minutes_left = context.job.data.get('minutes_left')
    if minutes_left is None:
        return
    if minutes_left > 0:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⏳ Còn {minutes_left} phút để giao dịch..."
        )
        if context.job_queue:
            context.job_queue.run_once(
                send_countdown_minute,
                60,
                chat_id=chat_id,
                data={'minutes_left': minutes_left - 1}
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🔔 **HẾT GIỜ!**\n❗️ **KHÔNG ĐƯỢC GIAO DỊCH!**\n⚠️ **Giao dịch là thua!**\n‼️ **Nếu cố tình giao dịch sẽ bị xử lý nghiêm khắc!**",
            parse_mode="Markdown"
        )

# Sửa welcome: nếu waiting_for_minute thì xử lý nhập phút, countdown, hiện nút Thắng/Thua
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not hasattr(update, "message") or not update.message:
        return
    if not hasattr(update, "effective_user") or update.effective_user is None:
        return
    user_id = update.effective_user.id if update.effective_user else None

    # Nếu user đang trong workflow, xử lý response
    if user_id in user_states:
        await handle_response(update, context)
        return

    # Nếu user chọn "Lịch sử giao dịch", gửi menu con
    if update.message.text == "Lịch sử giao dịch":
        keyboard = [
            [KeyboardButton("Lịch sử hôm nay")],
            [KeyboardButton("Lịch sử tuần này")],
            [KeyboardButton("Tất cả lịch sử")],
            [KeyboardButton("Quay lại menu")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("Chọn loại lịch sử muốn xem:", reply_markup=reply_markup)
        return

    # Xử lý các nút lịch sử con
    if update.message.text == "Lịch sử hôm nay":
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        results = []
        try:
            with open("history.txt", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith(today):
                        results.append(line.strip())
        except FileNotFoundError:
            results = []
        if results:
            await update.message.reply_text("Lịch sử hôm nay:\n" + "\n".join(results))
        else:
            await update.message.reply_text("Chưa có lịch sử giao dịch nào hôm nay.")
        return

    if update.message.text == "Lịch sử tuần này":
        today = datetime.datetime.now()
        start_week = today - datetime.timedelta(days=today.weekday())
        results = []
        try:
            with open("history.txt", "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        date_str = line.split("|")[0].strip().split(" ")[0]
                        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                        if start_week.date() <= date_obj.date() <= today.date():
                            results.append(line.strip())
                    except Exception:
                        continue
        except FileNotFoundError:
            results = []
        if results:
            await update.message.reply_text("Lịch sử tuần này:\n" + "\n".join(results))
        else:
            await update.message.reply_text("Chưa có lịch sử giao dịch nào tuần này.")
        return

    if update.message.text == "Tất cả lịch sử":
        results = []
        try:
            with open("history.txt", "r", encoding="utf-8") as f:
                results = [line.strip() for line in f]
        except FileNotFoundError:
            results = []
        if results:
            await update.message.reply_text("Tất cả lịch sử:\n" + "\n".join(results))
        else:
            await update.message.reply_text("Chưa có lịch sử giao dịch nào.")
        return

    if update.message.text == "Quay lại menu":
        keyboard = [
            [KeyboardButton("Vào")],
            [KeyboardButton("Lịch sử giao dịch")],
            [KeyboardButton("Kết quả thắng")],
            [KeyboardButton("Kết quả thua")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("Chào mừng! Chọn một chức năng bên dưới:", reply_markup=reply_markup)
        return

    if update.message.text == "Kết quả thắng":
        reasons = []
        try:
            with open("history.txt", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split("|")
                    if len(parts) >= 4 and parts[2].strip() == "Thắng":
                        reason = parts[3].strip()
                        if reason:
                            reasons.append(reason)
        except FileNotFoundError:
            reasons = []
        if reasons:
            # Sắp xếp theo bảng chữ cái và loại bỏ trùng lặp
            unique_reasons = sorted(set(reasons), key=lambda x: x.lower())
            formatted = [f"\U0001F3C6 *{r}*" for r in unique_reasons]
            max_len = 3500
            title = "Các lý do thắng trong lịch sử:\n"
            chunk = title
            for i, line in enumerate(formatted):
                if len(chunk) + len(line) + 1 > max_len:
                    await update.message.reply_text(chunk, parse_mode="Markdown")
                    chunk = title
                chunk += line + "\n"
            if chunk.strip() and chunk != title:
                await update.message.reply_text(chunk, parse_mode="Markdown")
        else:
            await update.message.reply_text("Chưa có lịch sử giao dịch thắng nào.")
        return

    if update.message.text == "Kết quả thua":
        reasons = []
        try:
            with open("history.txt", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split("|")
                    if len(parts) >= 4 and parts[2].strip() == "Thua":
                        reason = parts[3].strip()
                        if reason:
                            reasons.append(reason)
        except FileNotFoundError:
            reasons = []
        if reasons:
            # Sắp xếp theo bảng chữ cái và loại bỏ trùng lặp
            unique_reasons = sorted(set(reasons), key=lambda x: x.lower())
            formatted = [f"\U0001F480 *{r}*" for r in unique_reasons]
            max_len = 3500
            title = "Các lý do thua trong lịch sử:\n"
            chunk = title
            for i, line in enumerate(formatted):
                if len(chunk) + len(line) + 1 > max_len:
                    await update.message.reply_text(chunk, parse_mode="Markdown")
                    chunk = title
                chunk += line + "\n"
            if chunk.strip() and chunk != title:
                await update.message.reply_text(chunk, parse_mode="Markdown")
        else:
            await update.message.reply_text("Chưa có lịch sử giao dịch thua nào.")
        return

    # Nếu user nhấn "Vào" thì vào workflow
    if update.message.text == "Vào":
        user_states[user_id] = "step_1"
        await send_question(update, "step_1")
        return

    # Nếu user đang chờ nhập phút cho countdown
    if context.user_data is not None and context.user_data.get('waiting_for_minute'):
        context.user_data['waiting_for_minute'] = False
        if not update.message or not update.message.text:
            context.user_data['waiting_for_minute'] = True
            return
        try:
            phut_nhap = int(update.message.text.strip())
            if not (0 <= phut_nhap <= 59):
                await update.message.reply_text("Vui lòng nhập số phút từ 0 đến 59!")
                context.user_data['waiting_for_minute'] = True
                return
        except Exception:
            await update.message.reply_text("Vui lòng nhập số phút hợp lệ!")
            context.user_data['waiting_for_minute'] = True
            return
        phut_hien_tai = datetime.datetime.now().minute
        da_troi = so_phut_da_troi_qua(phut_nhap, phut_hien_tai)
        if da_troi >= 17:
            await update.message.reply_text("⛔️ Hết giờ giao dịch, không được vào lệnh!")
            return
        else:
            con_lai = 17 - da_troi
            countdown_next = context.user_data.get('countdown_next') if context.user_data else None
            options = {
                "Kết quả giao dịch: Thắng": "reason_win" if countdown_next == "should_trade" else "reason_win_short",
                "Kết quả giao dịch: Thua": "reason_lose" if countdown_next == "should_trade" else "reason_lose_short"
            }
            keyboard = [[KeyboardButton(opt)] for opt in options.keys()]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(
                f"✅ Hợp lệ! Còn {con_lai} phút để giao dịch.\n\nKhi xong, hãy chọn kết quả giao dịch:",
                reply_markup=reply_markup
            )
            # Đảm bảo user_id luôn được định nghĩa trước khi dùng
            user_id = update.effective_user.id if update.effective_user else None
            if user_id is not None:
                user_states[user_id] = countdown_next
            return TRADE_RESULT

    # Nếu không phải các trường hợp trên, hiển thị menu chính
    keyboard = [
        [KeyboardButton("Vào")],
        [KeyboardButton("Lịch sử giao dịch")],
        [KeyboardButton("Kết quả thắng")],
        [KeyboardButton("Kết quả thua")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Chào mừng! Chọn một chức năng bên dưới:",
        reply_markup=reply_markup
    )

async def ask_minute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return ConversationHandler.END
    await update.message.reply_text("Nhập phút big trader vào lệnh:")
    return ASK_MINUTE

async def handle_minute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return ASK_MINUTE
    try:
        phut_nhap = int(update.message.text.strip())
        if not (0 <= phut_nhap <= 59):
            await update.message.reply_text("Vui lòng nhập số phút từ 0 đến 59!")
            return ASK_MINUTE
    except Exception:
        await update.message.reply_text("Vui lòng nhập số phút hợp lệ!")
        return ASK_MINUTE
    phut_hien_tai = datetime.datetime.now().minute
    da_troi = so_phut_da_troi_qua(phut_nhap, phut_hien_tai)
    if da_troi >= 17:
        await update.message.reply_text("⛔️ Hết giờ giao dịch, không được vào lệnh!")
        return ConversationHandler.END
    else:
        con_lai = 17 - da_troi
        countdown_next = context.user_data.get('countdown_next') if context.user_data else None
        options = {
            "Kết quả giao dịch: Thắng": "reason_win" if countdown_next == "should_trade" else "reason_win_short",
            "Kết quả giao dịch: Thua": "reason_lose" if countdown_next == "should_trade" else "reason_lose_short"
        }
        keyboard = [[KeyboardButton(opt)] for opt in options.keys()]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            f"✅ Hợp lệ! Còn {con_lai} phút để giao dịch.\n\nKhi xong, hãy chọn kết quả giao dịch:",
            reply_markup=reply_markup
        )
        # Đảm bảo user_id luôn được định nghĩa trước khi dùng
        user_id = update.effective_user.id if update.effective_user else None
        if user_id is not None:
            user_states[user_id] = countdown_next
        return TRADE_RESULT

async def handle_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    if hasattr(query, 'data') and query.data == 'result_win':
        await query.edit_message_text("🎉 Chúc mừng bạn đã thắng! Nhập lý do:")
    elif hasattr(query, 'data') and query.data == 'result_lose':
        await query.edit_message_text("😢 Bạn đã thua! Nhập lý do:")
    # Hủy job countdown nếu đã chọn kết quả
    if context.user_data and 'countdown_job' in context.user_data:
        job = context.user_data.get('countdown_job')
        if job:
            job.schedule_removal()
    return ConversationHandler.END

async def notify_timeout_countdown(context: ContextTypes.DEFAULT_TYPE):
    if context.job and hasattr(context.job, 'chat_id') and context.job.chat_id is not None:
        await context.bot.send_message(
            chat_id=context.job.chat_id,
            text="🔔 **HẾT GIỜ!**\n❗️ **KHÔNG ĐƯỢC GIAO DỊCH!**\n⚠️ **Giao dịch là thua!**\n‼️ **Nếu cố tình giao dịch sẽ bị xử lý nghiêm khắc!**",
            parse_mode="Markdown"
        )

# Sửa handle_result_callback: hủy job countdown, chuyển sang nhập lý do và lưu lịch sử như cũ
async def handle_result_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    # Hủy job countdown nếu đã chọn kết quả
    if context.user_data and 'countdown_job' in context.user_data:
        job = context.user_data.get('countdown_job')
        if job:
            job.schedule_removal()
    trade_type = "Long"
    if context.user_data and context.user_data.get('countdown_next') == "should_short":
        trade_type = "Short"
    if context.user_data and context.user_data.get('waiting_for_reason'):
        waiting = context.user_data.get('waiting_for_reason')
        if waiting:
            result, trade_type = context.user_data.pop('waiting_for_reason')
            reason = update.message.text.strip() if update.message and update.message.text else ""
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            r_value = "1.67R"
            with open("history.txt", "a", encoding="utf-8") as f:
                f.write(f"{now} | {trade_type} | {result} | {reason} | {r_value}\n")
            keyboard = [
                [KeyboardButton("Vào")],
                [KeyboardButton("Lịch sử giao dịch")],
                [KeyboardButton("Kết quả thắng")],
                [KeyboardButton("Kết quả thua")],
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            if update.message:
                await update.message.reply_text(
                    "Đã lưu lịch sử lệnh! Chọn một chức năng bên dưới:",
                    reply_markup=reply_markup
                )
            return

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[],  # Không cần entry_points vì tích hợp vào workflow
        states={
            ASK_MINUTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_minute)],
            TRADE_RESULT: [CallbackQueryHandler(handle_result, pattern="^result_win$|^result_lose$")],
        },
        fallbacks=[CommandHandler("start", start)]
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, welcome))
    app.add_handler(CallbackQueryHandler(handle_result_callback, pattern="^result_win$|^result_lose$"))
    print("Bot đang chạy...")
    app.run_polling()

if __name__ == '__main__':
    main()

# Cách sửa: chỉ cần thay đổi phần WORKFLOW ở trên 