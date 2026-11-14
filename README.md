# Skylight Calendar for Home Assistant (unofficial)

Shows a [Skylight Calendar](https://ourskylight.com)'s chores, lists, events and reward points in Home Assistant.

It is **read-only**: it never changes anything on your Skylight.

> **Unofficial.** This project is not affiliated with, endorsed by, or supported by Skylight. It talks to the same private cloud API the Skylight apps use, which Skylight can change or block at any time. Using it may be against Skylight's terms of service. Use it at your own risk.

## What you get

One "Skylight" service with these entities. Names come from your own Skylight; "Alex" stands in for a family member here.

| Entity | Example | What it shows |
|---|---|---|
| To-do list per person | `todo.skylight_alex_chores` | Today's chores for that person, plus overdue ones. The state is the number still to do. Each item has its due date. |
| To-do list per Skylight list | `todo.skylight_grocery_list` | The items on that list, done and not done. |
| Calendar | `calendar.skylight_calendar` | Every event shown on the Skylight, including ones synced from Google, iCloud or Outlook. |
| Reward points per person | `sensor.skylight_alex_reward_points` | Current point balance. The lifetime total is in the `lifetime_points` attribute. |

A "person" is any Skylight profile that is selected for the chore chart.

Data refreshes every 5 minutes.

### Ideas

- Announce "Alex, you have 2 chores left" on a speaker at 6 pm.
- Show the family calendar and chore lists on a wall dashboard.
- Notify a parent when a child's chore list reaches zero.

## Requirements

- Home Assistant 2025.2 or newer. Developed and tested on 2026.11.
- A Skylight Calendar account with an email and password. If you normally sign in another way, set a password with **Forgot password?** on Skylight's login page first.

## Installation

### Marketplace or HACS (recommended)

1. In Home Assistant, open **Marketplace** (or HACS on older versions).
2. Open the menu and choose **Custom repositories**.
3. Add `https://github.com/masterpigg/ha-skylight` with the type **Integration**.
4. Find **Skylight Calendar (unofficial)** in the list and install it.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/skylight` folder from this repository into the `custom_components` folder inside your Home Assistant configuration folder.
2. Restart Home Assistant.

## Signing in

Skylight signs its own apps in through a web page that hands back a one-time code. That page only returns the code to Skylight's own website, which removes it from the address bar immediately. So you have to copy it from your browser's developer tools. It takes a minute, and you only do it once.

1. In Home Assistant, go to **Settings → Devices & services → Add integration** and pick **Skylight Calendar (unofficial)**. Leave that dialog open.
2. Open a new browser tab. Press **F12** to open the developer tools and switch to the **Network** tab.
3. Tick **Preserve log**, and type `welcome` in the filter box.
4. In that same tab, open the **Skylight's sign-in page** link from the Home Assistant dialog and log in.
5. A request named `welcome?code=...` appears in the Network tab. Right-click it and choose **Copy → Copy URL**.
6. Paste that address into the **Welcome address** box in Home Assistant and submit.

The code expires within a few minutes, so do steps 4 to 6 in one go. If Home Assistant says the code was rejected, close the dialog and start again; each attempt needs a fresh link.

Your password is only ever typed into Skylight's own page. Home Assistant stores an access token and a refresh token, and renews them by itself.

If your account has more than one Skylight, the integration uses the first one.

## When it stops working

**"Re-authenticate" appears on the integration.** Skylight rejected the stored tokens. Click it and repeat the sign-in steps.

**Entities go unavailable and the log mentions a retired API version.** Skylight requires every request to name an app version, and it switches old versions off from time to time. The log line reads `Skylight retired API version ...`. To fix it:

1. Find the version the current Skylight apps send. The value is a date such as `2026-10-15`, sent in a `Skylight-Api-Version` request header. Check this repository's issues and the [skylight-mcp](https://github.com/TheEagleByte/skylight-mcp) issues first, since someone has usually found it. Otherwise, sign in at [ourskylight.com](https://ourskylight.com) with the developer tools' Network tab open and look for that header on requests to `app.ourskylight.com`. Whether the web app sends it has not been confirmed.
2. Put that value in `API_VERSION` in `custom_components/skylight/const.py`.
3. Restart Home Assistant.

Please [open an issue](https://github.com/masterpigg/ha-skylight/issues) when this happens, so the default can be updated for everyone.

**Checking the API outside Home Assistant.** `tools/skylight_check.py` is a standalone, read-only script (Python 3.9+, no extra packages) that signs in and lists what each endpoint returns:

```bash
python tools/skylight_check.py start
```

Open the address it prints with the Network tab set up as described above, log in, then pass the copied welcome address back:

```bash
python tools/skylight_check.py finish "https://ourskylight.com/welcome?code=..."
```

It saves tokens to `skylight_tokens.json` next to the script. That file gives full access to your Skylight account. Delete it when you are done, and never commit it.

## Privacy and security

- The integration talks only to `app.ourskylight.com`.
- It makes `GET` requests for data. The only `POST` is to Skylight's token endpoint, to sign in and renew tokens.
- The stored tokens can do anything the Skylight app can, so treat your Home Assistant backups with the same care as your Skylight password.

## Limitations

- Read-only. You cannot tick off chores or add list items from Home Assistant.
- Chore lists show today's and overdue chores, not future ones.
- One Skylight per account (the first one).
- Meal plans, messages, rewards and the task box are not exposed yet.

## Credits

- [TheEagleByte/skylight-api](https://github.com/TheEagleByte/skylight-api) documented Skylight's API from captured network traffic.
- The OAuth sign-in and version header follow the community fix proposed in [TheEagleByte/skylight-mcp#48](https://github.com/TheEagleByte/skylight-mcp/pull/48).

## License

[MIT](LICENSE)
