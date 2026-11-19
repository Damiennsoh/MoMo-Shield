from app.api.demo_device import DemoDeviceEvent, _PHONE_PAGE


def test_demo_device_event_accepts_stable_card_key():
    event = DemoDeviceEvent(
        type="call",
        scenario="GH01",
        event_key="gh01|call|same-caller-digest",
        caller="024 555 0134",
        status="On call · 00:47",
    )
    assert event.event_key == "gh01|call|same-caller-digest"


def test_second_device_replaces_existing_keyed_cards_and_only_rings_for_new_call():
    assert "previous.replaceWith(card);return true;" in _PHONE_PAGE
    assert "const updated=add(card,event.event_key||'');" in _PHONE_PAGE
    assert "incoming&&(!updated||event.force_browser_ring)" in _PHONE_PAGE
    assert "event.event_key||((event.scenario||'')+'|warning')" in _PHONE_PAGE
    assert "const updated=add(card,event.event_key||((event.scenario||'')+'|warning'));" in _PHONE_PAGE
    assert "data-placeholder=\"waiting\"" in _PHONE_PAGE
    assert "placeholder.remove()" in _PHONE_PAGE
    assert "activeCall.classList.add('ended')" in _PHONE_PAGE
    assert "card.dataset.callStatus=callStatus" in _PHONE_PAGE
    assert "/missed|ended|declined/" in _PHONE_PAGE
    assert "/(incoming|ringing|on call|connected|answered)/" in _PHONE_PAGE
    assert "CALL ENDED · FRAUD INTERVENTION" in _PHONE_PAGE
    assert "Disconnected at simulated transaction hold" in _PHONE_PAGE
    assert "if(actions)actions.remove()" in _PHONE_PAGE


def test_second_device_audio_is_authenticated_sequential_and_sip_aware():
    assert "audioFiles={sms:['sms.mp3','sms.wav'],call:['ring.mp3','ring.wav']" in _PHONE_PAGE
    assert "audioLimits={sms:1.8,call:6,alert:1.2,warning:8}" in _PHONE_PAGE
    assert "'/api/v1/demo-device/audio/'" in _PHONE_PAGE
    assert "Authorization:'Bearer '+token" in _PHONE_PAGE
    assert "event.sip_managed&&!event.force_browser_ring" in _PHONE_PAGE
    assert "Browser speech muted to avoid competing with the local SIP call." in _PHONE_PAGE
    assert "warning_twi.mp3" in _PHONE_PAGE and "warning_en.wav" in _PHONE_PAGE
    assert "SpeechSynthesisUtterance" in _PHONE_PAGE and "en-GH" in _PHONE_PAGE
    assert "if(warningInProgress)await warningPlayback" in _PHONE_PAGE
