# JARVIS AI OMEGA — Voice E2E Validation

This checklist is the physical-device release gate for the emotional Indian voice system.
Automated tests, package healthchecks, configured voice names, and successful synthesis workers **do not** prove that a human heard correct audio or that a physical microphone recognized speech correctly.

## Candidate identity

Record before testing:

- Git commit SHA:
- Installer filename:
- Installer SHA-256:
- Windows version:
- PC/laptop model:
- Output device / speaker / headset:
- Input device / microphone:
- Network type:

Do not reuse evidence from another commit or installer build.

## 1. Installed runtime

- Install the exact release candidate on Windows.
- Launch `JARVIS-OMEGA.exe` normally.
- Run the packaged TTS runtime healthcheck.
- Confirm the configured profile is `indian-female-emotional`.
- Confirm the expected Indian voices are configured for English/Hinglish/Hindi.
- Confirm no API key or private runtime data is exposed in logs/output.

## 2. Audible Indian female voice

Use the normal desktop `VOICE TEST` and normal JARVIS replies, not a separate developer-only player.

Human-observe and record PASS/FAIL for:

- English: natural Indian female pronunciation.
- Hinglish: Roman-Hindi + English mixed sentence pronunciation.
- Hindi: Devanagari Hindi pronunciation.
- No clipping, repeated words, stuck playback, or silent success.
- Speech returns to IDLE after completion.

Recommended samples:

- English: `Good morning. JARVIS OMEGA is online and ready to assist.`
- Hinglish: `System ready hai. Aap bataiye ab kya karna hai.`
- Hindi: `नमस्ते। जार्विस ओमेगा ऑनलाइन है और आपकी मदद के लिए तैयार है।`

## 3. Emotion/prosody

Listen to each mode and verify the delivery is distinguishable but still natural:

- CALM — slower, composed delivery.
- HAPPY — slightly brighter/faster delivery.
- CONCERNED — slower, softer/serious delivery.
- URGENT — faster, firmer delivery without becoming unintelligible.
- PROFESSIONAL — steady, crisp delivery.

Record the exact text used for every observation. Do not mark an emotion VERIFIED solely because rate/pitch parameters were generated.

## 4. Sentence streaming and natural pauses

- Ask for a response containing at least five complete sentences.
- Confirm speech begins sentence-by-sentence rather than requiring one long full-answer TTS request.
- Confirm pauses between sentences sound intentional and not broken/stuttered.
- Confirm long sentences are split without losing or duplicating words.

## 5. Barge-in / interruption

While JARVIS is speaking a multi-sentence answer:

- Press push-to-talk and begin speaking.
- Confirm current TTS stops promptly.
- Confirm queued future speech from the interrupted answer does not continue over the user.
- Confirm the microphone records the new user request.
- Confirm JARVIS can speak normally again after the interruption.

## 6. Wake word

With wake-word mode explicitly enabled:

- Say `Hey JARVIS` followed by a command in the same utterance.
- Confirm the inline command is extracted and executed as a normal user request.
- While JARVIS is speaking, say the wake phrase; confirm speech yields to the user.
- Confirm unrelated background speech without the wake phrase does not become a command before a conversation window is active.

## 7. Limited continuous conversation

After one valid wake-word command:

- Speak a natural follow-up within the configured conversation window without repeating the wake phrase.
- Confirm the follow-up is accepted.
- Wait until the window expires.
- Speak another command without the wake phrase.
- Confirm it is ignored until the wake phrase is used again.

This is intentionally bounded; it is not an unrestricted always-on command mode.

## 8. Recognition languages

Test each with the same physical microphone:

- Indian English.
- Hinglish / Roman-Hindi style speech.
- Hindi.
- Normal room noise.
- One deliberately unclear utterance; confirm JARVIS reports recognition failure instead of inventing text.

## 9. Online voice failure and offline fallback

- Confirm online Edge neural voice works when network is available.
- Disconnect network or otherwise make the online synthesis path unavailable without modifying source code.
- Trigger speech.
- Confirm the offline fallback is attempted and JARVIS does not claim neural voice success when it failed.
- Restore network and confirm later neural speech can recover.

## 10. Repeated-use stability

Run at least 20 mixed voice interactions including:

- normal answers,
- stop,
- pause/resume,
- speed change,
- push-to-talk interruption,
- wake-word command,
- follow-up command,
- mute/unmute.

Confirm no stuck `SPEAKING` state, orphan audio, duplicate queued response, runaway worker, or inability to speak again.

## Evidence rule

A final voice release may be marked fully VERIFIED only when the exact candidate has both:

1. green automated source/package/installer regression evidence for the same SHA, and
2. this physical-device checklist completed with human-observed microphone and audible-speaker evidence.

Until item 2 exists, report physical microphone, audible playback, and perceived emotional quality as **NOT VERIFIED**, even when automated voice tests are green.
