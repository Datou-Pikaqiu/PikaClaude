import pika_claude


# 打印当前 pika_claude 包的版本号
def cmd_version() -> None:
    print(pika_claude.__version__)