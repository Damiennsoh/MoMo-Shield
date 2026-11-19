"""Mock victim handset renderer: SMS messenger, USSD screen, incoming call."""

import html

import streamlit as st


def _esc(s) -> str:
    return html.escape(str(s))


def _sms_bubbles(messages) -> str:
    out = []
    for m in messages:
        cls = "bubble in" if m.get("dir") == "in" else "bubble out"
        sender = (f'<div class="bubble-from">{_esc(m.get("from", ""))}</div>'
                  if m.get("dir") == "in" else "")
        out.append(
            f'<div class="{cls}">{sender}'
            f'<div class="bubble-text">{_esc(m.get("text", ""))}</div></div>'
        )
    return f'<div class="sms-list">{"".join(out)}</div>'


def _call_screen(state) -> str:
    caller = state.get("caller", "Unknown Number")
    transcript = state.get("transcript")
    t_html = (f'<div class="call-transcript">{_esc(transcript)}</div>'
              if transcript else "")
    return f"""
    <div class="call-screen">
      <div class="call-label">MTN · {_esc(state.get('call_type', 'voice'))}</div>
      <div class="call-avatar">{_esc(str(caller)[0])}</div>
      <div class="call-number">{_esc(caller)}</div>
      <div class="call-status">{_esc(state.get('call_status', 'Ringing…'))}</div>
      {t_html}
      <div class="call-actions">
        <span class="call-btn decline">✕</span>
        <span class="call-btn accept">✓</span>
      </div>
    </div>"""


def _ussd_screen(state) -> str:
    lines = state.get("ussd_lines", ["*170#", "1) Transfer Money", "2) Buy Airtime"])
    body = "<br>".join(_esc(line) for line in lines)
    return f'<div class="ussd-screen">{body}</div>'


def _home_screen() -> str:
    return """
    <div class="phone-home">
      <div class="home-clock">10:14</div>
      <div class="home-date">Thursday, 26 November</div>
      <div class="home-hint">Awaiting sandbox events…</div>
    </div>"""


def _warning_html(warning) -> str:
    variant = " watch" if warning.get("variant") == "watch" else ""
    icon = "🛡️" if variant else "⚠️"
    call_ended = ('<div class="warn-call-ended">☎ Call disconnected at FraudOps intervention</div>'
                  if warning.get("call_ended") else "")
    return f"""
    <div class="phone-warning{variant}" role="status" aria-live="polite">
      <div class="warn-title">{icon} {_esc(warning.get('title', 'FRAUD ALERT'))}</div>
      <div class="warn-body">{_esc(warning.get('body', ''))}</div>
      {call_ended}
    </div>"""


def phone_markup(state: dict) -> str:
    """Return one complete, correctly nested HTML fragment for the handset."""
    screen = state.get("screen", "home")
    if screen == "sms":
        body = _sms_bubbles(state.get("sms", []))
    elif screen == "call":
        body = _call_screen(state)
    elif screen == "ussd":
        body = _ussd_screen(state)
    else:
        body = _home_screen()

    warning = _warning_html(state["warning"]) if state.get("warning") else ""
    markup = f"""
    <div class="phone-frame">
      <div class="phone-notch"></div>
      <div class="phone-statusbar"><span>MTN · Ghana</span><span>LTE ▂▄▆█ 🔋</span></div>
      <div class="phone-body">
        {body}
        {warning}
      </div>
      <div class="phone-caption">Victim handset (simulated — what the customer sees, in real time)</div>
    </div>
    """
    # Markdown interprets deeply indented HTML lines as code blocks even when
    # unsafe HTML is enabled. Compact the *complete* interpolated fragment so
    # every screen, warning, and caption is rendered as one HTML block.
    return " ".join(markup.split())


def render_phone(state: dict, target=None):
    """Render the full phone frame. `state` keys: screen, sms, caller,
    call_status, transcript, ussd_lines, warning.

    Compact markup before sending it through unsafe-HTML Markdown: Markdown
    treats deeply indented nested ``<div>`` lines as code blocks, which exposed
    the warning markup literally in the phone UI. ``target`` is a Streamlit
    container/placeholder used by the live replay to replace the same element.
    """
    container = target if target is not None else st
    container.markdown(phone_markup(state), unsafe_allow_html=True)
