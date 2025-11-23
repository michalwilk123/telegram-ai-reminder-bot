# Coding Rules

## Core Principles

- Design functions with simple input arguments and simple return values.
- Write redundant code if it improves readability. Do not write preemptively extensible code.
- Write functional code. Do not create classes when functions suffice.

## Code Clarity

- Do not use default arguments for internal functions. Make all internal function calls explicit.
-Do not use None as an argument type. Resolve unknown arguments immediately.
- Split complex logic into multiple functions. Code becomes hard to understand when if statements, for loops, and try-except blocks appear in close proximity. Break these into separate functions.

## Validation and Safety

- Validate all inputs at the entry point. Fail fast.
- Write pure functions. Eliminate side effects and mutable state wherever possible.
- Do not use global state.

## Import and Structure Rules

- Place all imports at the top of the file. Do not use local imports or function definitions inside if statements, function definitions, or try blocks.
- Do not use relative paths. Do not reference `__file__`.
- Do not write comments or docstrings. The code is the documentation.

## Project Structure

**ui/** - Contains code that relates to the interaction with the user. For example: CLI, jupyter notebooks, telegram, api server, mcp. Main problem domains: interaction with user, error handling and logging
**core/** - Contains application-specific logic. The functions should ideally not rely on any external state. Not designed for reusability. The reasoning behind those functions is to make the code better to understand. Application-wide common functions go in `core/common.py`
**managers/** - Interfaces for external libraries and applications (git, sqlite, external services, etc.). Only managers communicate with external applications directly.
**utils.py or utils/** - Universal logic unrelated to the project domain. Those function should be reusable. Main rule of thumb should be: if the function seems to be useful for standard python library, it should be in utils and not in core.
**handlers.py or handlers.py** - logic that is responsible for connection the code from ui, core, managers, validation and utils. Only this code access all the code. Rest of the code should either call function from it, all be called from it. This code will actually store the business logic of the application.
**validation.py** - validation logic

Managers interface with external applications. Core functions use managers. CLI directory does not contain application logic.

## Technical Stack

- **uv** for running the project
- **pytest** for testing
- **marimo** very basic manual testing of functionalities

