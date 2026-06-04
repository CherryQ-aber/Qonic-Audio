# 主程序入口
from logger import logger
from watcher import start_watch


def main():
    logger.info("音频转换器启动成功")
    start_watch()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
