/** Explicit deployment choice; ordinary desktop installs keep native ASR. */
export const cloudSpeechEnabled=()=>process.env.NEXT_PUBLIC_ATTUNE_SPEECH_PROVIDER==='openai';
export const CLOUD_SPEECH_PERMISSION='cloud-asr-openai-v1';
export const CLOUD_SPEECH_COPY='Attune.more\'nun konuşmamı tanıması için mikrofon sesimin bulut hizmetine gönderilmesine izin veriyorum. Bu hizmeti OpenAI sağlar ve kendi veri işleme koşulları geçerlidir. Attune.more ham sesi kaydetmez.';
