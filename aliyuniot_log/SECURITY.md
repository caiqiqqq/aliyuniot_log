# Security Policy

## Sensitive Data

This project is intended to run locally. It can process real Alibaba Cloud IoT
console data, including device IDs, TraceIDs, status values, and log content.

Do not publish:

- `.env`
- `data/iot_logs.db`
- `data/`
- `artifacts/`
- Chrome profiles, cookies, storage state, or exported analysis files

The Chrome extension does not store login cookies. It reads the currently open
Alibaba Cloud IoT console page and sends collected table/search data to the
local API configured in the extension.

## Reporting Issues

If you find a security issue, do not open a public issue with sensitive details.
Open a minimal issue asking for a private contact channel, or contact the
maintainers through the repository owner's preferred contact method.

## Recommended Use

- Use a low-privilege Alibaba Cloud RAM user when possible.
- Run the local API on `127.0.0.1`.
- Review exported CSV/JSON before sharing.
- Clear `data/` before publishing or packaging the project.
