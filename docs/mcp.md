# AR3 as an MCP tool

`ar3_mcp.py` runs AR3 as a [Model Context Protocol](https://modelcontextprotocol.io) server over stdio,
so any AI agent can ask it whether a failed payment is safe to retry.

It exposes one tool, `decide_failed_payment`, which takes the PayPal error code (plus the optional
description, method, channel, attempt number, USD amount and payment id) and returns AR3's decision
together with an `agent_instruction` sentence: "Do not retry this payment.", "Retry once now with the
same PayPal-Request-Id: ...", and so on.

Known error codes are answered by the rule table instantly. Unknown ones go to Nemotron on Nebius
Token Factory, then through the same safety checks as everywhere else. AR3 never moves money.

## Add it to Claude Desktop

Open `claude_desktop_config.json` (Claude Desktop → Settings → Developer → Edit Config) and add AR3
next to any other servers:

```json
{
  "mcpServers": {
    "ar3": {
      "command": "python",
      "args": ["<full path>/ar3_mcp.py"]
    }
  }
}
```

Use the absolute path to `ar3_mcp.py`, for example `/Users/you/projects/ar3/ar3_mcp.py` on macOS or
`C:/Users/you/projects/ar3/ar3_mcp.py` on Windows. Restart Claude Desktop; the tool list should now
include `decide_failed_payment`.

## Keys

The server reads the same `.env` as the app, and only needs the key for the model tier it reaches:

- `NEBIUS_API_KEY` — required for unknown error codes (the Nemotron call). Known codes work without it.
- `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` — not needed here; they are only for the live PayPal tab.

Keep `.env` next to `ar3_mcp.py`, or set the variables in the environment Claude Desktop starts it in.

## Run it by hand

```bash
python ar3_mcp.py
```

It waits on stdio for MCP requests. Press Ctrl+C to stop it.
