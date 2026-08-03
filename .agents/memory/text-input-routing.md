---
name: Telegram text-input routing
description: The bot uses one central text dispatcher for all callback-followup input flows.
---

All non-command text input must pass through the single dispatcher in the bot entry point, which routes to existing feature handlers in priority order. Feature modules should register callback handlers only, and every imported input handler must exist before wiring it into the dispatcher.

**Why:** A callback button and the user's typed reply are different Telegram update types; duplicate or invalid feature-level text registrations can swallow replies or crash routing before any feature handler runs.

**How to apply:** When adding a new prompt, add its state and handler, import that handler in the central dispatcher path, and verify the callback → typed message → persistence → confirmation flow with a mocked update.