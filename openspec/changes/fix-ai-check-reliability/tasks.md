## 1. Scheduler and single-flight

- [x] 1.1 Skip startup and interval scheduling when provider or model is unset
- [x] 1.2 Ignore a new check while `running` is true, and always clear `running` in `finally`
- [x] 1.3 Add timeouts to Gemini, OpenAI, and Ollama HTTP calls

## 2. Credentials and parsing

- [x] 2.1 Send the Gemini API key in a header and remove it from request URLs
- [x] 2.2 Coerce string list-fields to a single entry and ignore non-list values
- [x] 2.3 Strip Markdown fences as whole lines without stripping backticks inside JSON
- [x] 2.4 Omit `raw_response` from diagnostics
- [x] 2.5 Add provider, model, API key, and base URL to the options flow, keeping a blank key

## 3. Tests

- [x] 3.1 Setup with no provider does not schedule a startup check
- [x] 3.2 A second check does not call the provider while one is running
- [x] 3.3 `"issues": "tip burn"` stores one issue
- [x] 3.4 Gemini request URL does not contain `key=`
- [x] 3.5 A blank options API key leaves the stored key in place
- [x] 3.6 Diagnostics payload has no `raw_response`
