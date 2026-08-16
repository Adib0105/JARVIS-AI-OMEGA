from jarvis import __version__
from jarvis.updater import check_latest_release


if __name__ == '__main__':
    try:
        result = check_latest_release(__version__)
        print(result['message'])
        if result.get('url'):
            print(result['url'])
    except Exception as exc:
        print(f'Update check failed: {exc}')
