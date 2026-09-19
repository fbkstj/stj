"""讓 Windows 終端機（cp950）印中文與符號時不會當掉。每個進入點開頭呼叫 setup()。"""
import logging
import sys


def setup(level=logging.INFO) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s：%(message)s",
                        datefmt="%H:%M:%S")
