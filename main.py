import logging
import pandas as pd
import random
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler

# Bot Constants
TOKEN = "7014456931:AAE5R6M9wgfMMyXPYCdogRTISwbaUjSXQRo"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1QMKiohAaO5QtHoQwBX5efTXCI_Q791A4GnoCe9nMV2w/export?format=csv&sheet=TTCK"

# States
QUIZ, WAIT_ANSWER = range(2)

# Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Load Questions
def load_questions():
    try:
        data = pd.read_csv(SHEET_URL)
        questions = data.to_dict(orient="records")
        random.shuffle(questions)
        return questions[:20]
    except Exception as e:
        logger.error(f"Error loading questions: {e}")
        return []

# Start Command
def start(update: Update, context: CallbackContext):
    context.user_data["questions"] = load_questions()
    context.user_data["current_question"] = 0
    context.user_data["score"] = 0
    if not context.user_data["questions"]:
        update.message.reply_text("⚠️ Không thể tải câu hỏi. Vui lòng thử lại sau.")
        return ConversationHandler.END

    update.message.reply_text(
        "🎉 Chào mừng bạn đến với Gameshow 'Ai Là Thiên Tài Đầu Tư’'!\n\n"
        "📜 *Luật chơi:*\n"
        "- Có 20 câu hỏi.\n"
        "- Mỗi câu trả lời đúng được 1 điểm.\n"
        "- Nếu không trả lời trong 60 giây, bạn sẽ bị tính 0 điểm.\n\n"
        "🔥 Bạn đã sẵn sàng? Nhấn /quiz để bắt đầu trả lời các câu hỏi!"
    )
    return QUIZ

# Ask Next Question
def ask_question(update: Update, context: CallbackContext):
    user_data = context.user_data
    current = user_data["current_question"]
    questions = user_data["questions"]

    # Hủy job timeout cũ nếu tồn tại
    if "timeout_job" in user_data and user_data["timeout_job"] is not None:
        user_data["timeout_job"].schedule_removal()

    if current < len(questions):
        question = questions[current]
        options = [question["Option 1"], question["Option 2"], question["Option 3"]]
        user_data["current_question"] += 1

        reply_markup = ReplyKeyboardMarkup([[1, 2, 3]], one_time_keyboard=True)
        update.message.reply_text(
            f"💬 Câu {current + 1}: {question['Question']}\n\n"
            f"1️⃣ {options[0]}\n"
            f"2️⃣ {options[1]}\n"
            f"3️⃣ {options[2]}",
            reply_markup=reply_markup,
        )

        # Đặt timeout mới
        timeout_job = context.job_queue.run_once(timeout_handler, 60, context=update.message.chat_id)
        user_data["timeout_job"] = timeout_job
        return WAIT_ANSWER
    else:
        finish_quiz(update, context)
        return ConversationHandler.END

# Timeout Handler
def timeout_handler(context: CallbackContext):
    chat_id = context.job.context
    bot = context.bot

    # Lấy thông tin người dùng từ user_data
    user_data = context.dispatcher.user_data.get(chat_id, {})
    current = user_data.get("current_question", 0)
    questions = user_data.get("questions", [])

    # Nếu còn câu hỏi, thông báo hết thời gian và chuyển sang câu tiếp theo
    if current < len(questions):
        bot.send_message(
            chat_id=chat_id,
            text=f"⏳ Hết thời gian cho câu này! Tổng điểm hiện tại của bạn là {user_data['score']}/20."
        )
        # Vô hiệu hóa khả năng trả lời cho câu hỏi này
        user_data["timeout_job"] = None
        # Chuyển sang câu hỏi tiếp theo
        ask_question_via_context(context, chat_id)
    else:
        # Kết thúc quiz nếu đây là câu cuối
        finish_quiz_via_context(context, chat_id)

    # Kiểm tra nếu người dùng trả lời sau khi hết thời gian
    if "timeout_job" in user_data and user_data["timeout_job"] is None:
        update.message.reply_text("⏳ Bạn đã hết thời gian trả lời câu hỏi này. Chuyển sang câu hỏi tiếp theo!")
        return WAIT_ANSWER

    try:
        user_answer = int(update.message.text)
    except ValueError:
        update.message.reply_text("⚠️ Vui lòng chọn 1, 2 hoặc 3.")
        return WAIT_ANSWER

    correct_answer = int(questions[current]["Answer"])

    if user_answer == correct_answer:
        user_data["score"] += 1
        update.message.reply_text(f"👍Chính xác! Tổng điểm của bạn hiện tại là {user_data['score']}/20.")
    else:
        update.message.reply_text(
            f"😥 Sai rồi! Đáp án đúng là {correct_answer}. "
            f"Tổng điểm hiện tại của bạn là {user_data['score']}/20."
        )

    ask_question(update, context)

# Ask Question via Context
def ask_question_via_context(context: CallbackContext, chat_id):
    user_data = context.dispatcher.user_data[chat_id]
    current = user_data.get("current_question", 0)
    questions = user_data.get("questions", [])

    # Hủy job timeout cũ nếu tồn tại
    if "timeout_job" in user_data and user_data["timeout_job"] is not None:
        user_data["timeout_job"].schedule_removal()

    if current < len(questions):
        question = questions[current]
        options = [question["Option 1"], question["Option 2"], question["Option 3"]]
        user_data["current_question"] += 1

        context.bot.send_message(
            chat_id=chat_id,
            text=f"💬 *Câu {current + 1}:* {question['Question']}\n\n"
                 f"1️⃣ {options[0]}\n"
                 f"2️⃣ {options[1]}\n"
                 f"3️⃣ {options[2]}",
            reply_markup=ReplyKeyboardMarkup([[1, 2, 3]], one_time_keyboard=True),
        )

        # Đặt timeout mới
        timeout_job = context.job_queue.run_once(timeout_handler, 60, context=chat_id)
        user_data["timeout_job"] = timeout_job
    else:
        finish_quiz_via_context(context, chat_id)
# Handle Answer
def handle_answer(update: Update, context: CallbackContext):
    user_data = context.user_data
    current = user_data["current_question"] - 1
    questions = user_data["questions"]

    try:
        user_answer = int(update.message.text)
    except ValueError:
        update.message.reply_text("⚠️ Vui lòng chọn 1, 2 hoặc 3.")
        return WAIT_ANSWER

    correct_answer = int(questions[current]["Answer"])

    if user_answer == correct_answer:
        user_data["score"] += 1
        update.message.reply_text(f"👍 Chính xác! Tổng điểm của bạn hiện tại là {user_data['score']}/20.")
    else:
        update.message.reply_text(
            f"😥 Sai rồi! Đáp án đúng là {correct_answer}. "
            f"Tổng điểm hiện tại của bạn là {user_data['score']}/20."
        )

    # Kiểm tra nếu đây là câu hỏi cuối cùng
    if current + 1 == len(questions):
        finish_quiz(update, context)
        return ConversationHandler.END
    else:
        ask_question(update, context)

# Finish Quiz
def finish_quiz(update: Update, context: CallbackContext):
    user_data = context.user_data
    score = user_data.get("score", 0)

    if score >= 15:
        result = "🥇 Nhà đầu tư thiên tài!"
    elif 12 <= score < 15:
        result = "🥈 Nhà đầu tư tiềm năng!"
    else:
        result = "🥉 Thế giới rất rộng lớn và còn nhiều thứ phải học thêm."

    update.message.reply_text(
        f"🎉 *Chúc mừng bạn đã hoàn thành cuộc thi 'Ai Là Thiên Tài Đầu Tư’'!*\n\n"
        f"🏆 *Tổng điểm của bạn:* {score}/20.\n{result}"
    )

# Main Function
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            QUIZ: [CommandHandler("quiz", ask_question)],
            WAIT_ANSWER: [MessageHandler(Filters.regex("^[1-3]$"), handle_answer)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    dp.add_handler(conv_handler)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()