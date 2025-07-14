"""
指令路由器模組
負責根據使用者輸入，將任務分派給對應的指令處理器。
"""
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.webhooks import MessageEvent
from .commands.help_handler import HelpCommandHandler
from .commands.clear_memory_handler import ClearMemoryHandler
from .commands.draw_handler import DrawCommandHandler
from .commands.todo_handler import TodoCommandHandler
from .commands.url_handler import URLHandler
from .commands.ai_intent_handler import AIIntentHandler
from utils.logger import get_logger

logger = get_logger(__name__)


class Router:
    """
    一個路由器，根據指令將事件分派給不同的處理器。
    """

    def __init__(self, services: dict, configuration: Configuration):
        self.configuration = configuration
        # 初始化所有指令處理器，傳遞 configuration 而不是 line_bot_api
        self.help_handler = HelpCommandHandler(configuration)
        self.clear_memory_handler = ClearMemoryHandler(
            services['storage'], configuration)
        self.draw_handler = DrawCommandHandler(
            services['image'], services['storage'], configuration)
        self.todo_handler = TodoCommandHandler(
            services['storage'], configuration)
        self.url_handler = URLHandler(
            services['web'], services['text'], configuration)
        self.ai_intent_handler = AIIntentHandler(
            services['parsing'],
            services['text'],
            services['storage'],
            services['weather'],
            services['news'],
            services['stock'],
            services['calendar'],
            configuration)
        # ... 未來會在這裡初始化其他處理器

        # 定義指令與處理器的映射關係
        self.keyword_routes = {
            ("功能說明", "help", "幫助", "指令"): self.help_handler.handle,
            ("清除對話", "忘記對話", "清除記憶"): self.clear_memory_handler.handle,
            ("待辦清單", "我的待辦", "todo list"): self.todo_handler.handle_list,
        }
        # 定義前綴指令與處理器的映射關係
        self.prefix_routes = {
            "畫": self.draw_handler.handle,
            "新增待辦": self.todo_handler.handle_add,
            "todo": self.todo_handler.handle_add,
            "完成待辦": self.todo_handler.handle_complete,
            "done": self.todo_handler.handle_complete,
        }

    def route(self, event: MessageEvent) -> bool:
        """
        根據文字訊息內容，將事件路由到對應的處理器。
        如果成功路由，返回 True，否則返回 False。
        """
        user_id = event.source.user_id
        user_message = event.message.text.strip()
        reply_token = event.reply_token

        # 優先檢查 URL，因為它很明確
        if self.url_handler.is_url_message(user_message):
            try:
                self.url_handler.handle(user_id, user_message)
                logger.info("Routed URL message to URLHandler.")
                return True
            except Exception as e:
                logger.error(
                    "Error executing URLHandler for message '%s': %s",
                    user_message,
                    e,
                    exc_info=True)
                return True

        # 檢查關鍵字路由
        for keywords, handler_method in self.keyword_routes.items():
            if user_message in keywords:
                try:
                    if 'user_id' in handler_method.__code__.co_varnames:
                        handler_method(
                            user_id=user_id,
                            reply_token=reply_token)
                    else:
                        handler_method(reply_token=reply_token)
                    logger.info(
                        "Routed keyword command '%s' to a handler.",
                        user_message)
                    return True
                except Exception as e:
                    logger.error(
                        "Error executing keyword handler for command '%s': %s",
                        user_message,
                        e,
                        exc_info=True)
                    return True

        # 檢查前綴路由
        for prefix, handler_method in self.prefix_routes.items():
            # 使用 lower() 來進行不分大小寫的比對
            if user_message.lower().startswith(prefix):
                try:
                    # 提取指令後的內容
                    content = user_message[len(prefix):].strip()

                    # 根據 handler 的簽名傳遞參數
                    handler_args = handler_method.__code__.co_varnames
                    params = {'user_id': user_id, 'reply_token': reply_token}
                    if 'item' in handler_args:
                        params['item'] = content
                    if 'prompt' in handler_args:
                        params['prompt'] = content
                    if 'text' in handler_args:
                        params['text'] = user_message  # 傳遞原始訊息以供解析

                    handler_method(**params)
                    logger.info(
                        "Routed prefix command '%s' to a handler.",
                        user_message)
                    return True
                except Exception as e:
                    logger.error(
                        "Error executing prefix handler for command '%s': %s",
                        user_message,
                        e,
                        exc_info=True)
                    return True

        # 如果以上都沒有匹配，則進入 AI 意圖判斷
        if self.ai_intent_handler.handle(user_id, user_message):
            logger.info(
                "Routed message '%s' to AIIntentHandler.",
                user_message)
            return True

        return False  # 如果 AI 意圖判斷也未處理，則返回 False
