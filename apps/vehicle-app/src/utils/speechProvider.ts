/** Explicit deployment choice; ordinary desktop installs keep native ASR. */
export const cloudSpeechEnabled=()=>process.env.NEXT_PUBLIC_ATTUNE_SPEECH_PROVIDER==='openai';
export const CLOUD_SPEECH_PERMISSION='cloud-asr-openai-v1';
export const CLOUD_SPEECH_COPY='Konuşma tanıma için mikrofon sesimin OpenAI bulut hizmetine gönderilmesine izin veriyorum. Attune.more ham sesi kaydetmez; sağlayıcının veri işleme koşulları geçerlidir.';
