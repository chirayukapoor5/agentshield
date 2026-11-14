import asyncio

from .server import create_server


def main() -> None:
    asyncio.run(create_server().run_stdio_async())


if __name__ == "__main__":
    main()
