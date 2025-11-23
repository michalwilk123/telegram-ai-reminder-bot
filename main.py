import argparse
import subprocess
import sys


def run_command(command: list[str], description: str) -> bool:
    print(f'\n{"=" * 60}')
    print(f'Running: {description}')
    print(f'{"=" * 60}\n')

    # Prepend 'uv run' to ensure commands run in the project's environment
    full_command = ['uv', 'run'] + command

    try:
        result = subprocess.run(full_command)

        if result.returncode != 0:
            print(f'\n❌ {description} failed with exit code {result.returncode}')
            return False

        print(f'\n✓ {description} completed successfully')
        return True
    except FileNotFoundError:
        print("\n❌ Error: Could not find 'uv' executable. Please ensure uv is installed.")
        return False
    except KeyboardInterrupt:
        print(f'\n\n⚠️ {description} interrupted by user')
        return False


def cmd_run(args) -> int:
    """Run the application server."""
    success = run_command(['python', 'server.py'], 'Development Server')
    return 0 if success else 1


def cmd_lint(args) -> int:
    """Run linters and formatters."""
    print('Starting code linting...')

    commands = [
        (['ruff', 'check', '--fix', '.'], 'Ruff fix'),
        (['ruff', 'format', '.'], 'Ruff format'),
        # Vulture finds unused code.
        # We target the current directory '.'.
        # You might want to add a whitelist.py if you have one.
        (['vulture', '.'], 'Vulture dead code check'),
    ]

    all_passed = True
    for command, description in commands:
        if not run_command(command, description):
            all_passed = False

    print(f'\n{"=" * 60}')
    if all_passed:
        print('✓ All linting checks passed')
        print(f'{"=" * 60}\n')
        return 0
    else:
        print('❌ Some linting checks failed')
        print(f'{"=" * 60}\n')
        return 1


def cmd_test(args) -> int:
    """Run tests."""
    success = run_command(['pytest', '-v'], 'Pytest')
    return 0 if success else 1


def cmd_system_test(args) -> int:
    """Run system test."""
    success = run_command(['python', 'system_test.py'], 'System Test')
    return 0 if success else 1


def cmd_check(args) -> int:
    """Run type checking with mypy."""
    success = run_command(['mypy', '.'], 'Type Checking (mypy)')
    return 0 if success else 1


def main():
    parser = argparse.ArgumentParser(
        description='Project management CLI for Reminder App (powered by uv)'
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    subparsers.required = True

    # Run command
    parser_run = subparsers.add_parser('run', help='Run the development server')
    parser_run.set_defaults(func=cmd_run)

    # Lint command
    parser_lint = subparsers.add_parser('lint', help='Run linters and formatters (ruff, vulture)')
    parser_lint.set_defaults(func=cmd_lint)

    # Test command
    parser_test = subparsers.add_parser('test', help='Run tests (pytest)')
    parser_test.set_defaults(func=cmd_test)

    # System test command
    parser_system_test = subparsers.add_parser(
        'system-test', help='Run system test (full integration test)'
    )
    parser_system_test.set_defaults(func=cmd_system_test)

    # Check command
    parser_check = subparsers.add_parser('check', help='Run type checking (mypy)')
    parser_check.set_defaults(func=cmd_check)

    args = parser.parse_args()

    if hasattr(args, 'func'):
        sys.exit(args.func(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
