param([Parameter(Mandatory)][string]$OutDir)
# Controlled German answer for the real-browser Vision journey, from the Windows voice installed
# on this machine: local, free, no network. It proves the speech path only; it is not a person,
# and the recognition result still comes from the browser's own recognizer.
Add-Type -AssemblyName System.Speech
$voice = 'Microsoft Hedda Desktop'
$text = 'Ich sehe es nicht.'
New-Item -ItemType Directory -Force $OutDir | Out-Null
$path = Join-Path $OutDir 'vision-not-visible-de.wav'
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice($voice)
$synth.Rate = -1
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(24000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$synth.SetOutputToWaveFile($path, $format)
$prompt = New-Object System.Speech.Synthesis.PromptBuilder
$prompt.AppendBreak([TimeSpan]::FromMilliseconds(300))
$prompt.AppendText($text)
$prompt.AppendBreak([TimeSpan]::FromMilliseconds(400))
$synth.Speak($prompt)
$synth.SetOutputToNull()
$synth.Dispose()
@{ text = $text; voice = $voice; engine = 'Windows System.Speech'; network = $false; paidService = $false; sha256 = (Get-FileHash $path -Algorithm SHA256).Hash.ToLower(); bytes = (Get-Item $path).Length } | ConvertTo-Json | Set-Content (Join-Path $OutDir 'german-provenance.json') -Encoding utf8
Get-Content (Join-Path $OutDir 'german-provenance.json')
