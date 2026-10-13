# MUSIC 02 — M02-T001

Importação, análise e primeiro preview concluídos. Validação objetiva: **PASS**. Avaliação perceptiva: **PENDENTE**.

## Ouvir primeiro

- [Binaural level-matched — 200–230 s](../renders/M02_T001_binaural_200_230_level_matched_24bit.wav)
- [Dry level-matched — 200–230 s](../renders/M02_T001_dry_comparison_200_230_level_matched_24bit.wav)
- [Other isolado para identificação](../renders/M02_T001_Other_identification_200_230_raw.wav)

Ambas as comparações medem −20,6 LUFS (resolução de relatório: 0,1 LU). Binaural: sample peak/true peak −6,0 dBFS/dBTP; dry matched: −7,31 dBFS / −7,3 dBTP. Duração exata: 30 s / 1.440.000 frames, estéreo PCM24 a 48 kHz. Não houve limiter, compressão ou mastering.

## Auditoria dos originais

11 stems; 48 kHz; PCM16; estéreo; 11.884.801 frames; 247,600020833 s. Nenhuma amostra no limiar de clipping detectado. Nenhum arquivo foi convertido, deslocado, resampleado, normalizado ou cortado. Silêncios geraram apenas metadados. Igualdade de frames preserva a origem temporal dos arquivos; não prova, por si só, o alinhamento da gravação na ausência de timecode.

| Role | Arquivo | Pico dBFS | SHA-256 |
|---|---|---:|---|
| lead_vocal | 0 Lead Vocals.wav | -2.83 | `129be5ea46725dbcae3e8c892d1ec8b3926f089846377043cd0118ce98577c09` |
| backing_vocals | 1 Backing Vocals.wav | -3.20 | `988da51c233857a137830cc5be97502e73c0ed84acfab38ff80dedf070259032` |
| woodwinds | 10 Woodwinds.wav | -9.78 | `8e5320a183713ac6229bb69098ec659fd6319303aaeec6ae2862f70e8df8aa31` |
| drums | 2 Drums.wav | -3.16 | `e9f75d4075444f51037bf5c533d69bb12c5a2e1646a9ce79db28672047376945` |
| bass | 3 Bass.wav | -5.92 | `d4e60bd2b805db054275cba155c77b9b5532711c373f7ac909bd3585ecdd0ba2` |
| guitar | 4 Guitar.wav | -4.93 | `dc9025dc14e7060f8855d7792e45e6bb8880facdbd4b95f4a8e6ae847d14b503` |
| keyboards | 5 Keyboard.wav | -11.72 | `b7a5e34f024de7682fc3da5a3604c5843ce8a34d45d24011f22e0ca7ed0962ab` |
| percussion | 6 Percussion.wav | -3.14 | `25f6a6d514b0fb2a4eedd5837c7f19681b1106b06b70a7d2c36a3f50b38747a4` |
| synth | 7 Synth.wav | -4.98 | `70b4f1eef42aae192d3ca855ff87c12f4e36df04121ab6b0d3fd4e548ad3207a` |
| other | 8 Other.wav | -4.48 | `1e8f246094e9f6c9132a864f568ffe5b8c4ba80462ec76ec1aeddbc8b9c236de` |
| brass | 9 Brass.wav | -13.11 | `7d1483ef72e6046bde4121fb5d3246a9ed49aa06b7c036f7da9b5a2296677f96` |

## Análise musical

BPM recalculado: **108.173077**. Drums e Percussion concordam independentemente. O método é autocorrelação de onsets com hop de 1024 frames; a confiança 1,0 é contraste normalizado, não probabilidade estatística. A resolução de lag é limitada; não se deve interpretar seis casas decimais como precisão do tempo musical.

Hipótese de métrica: 4/4 (confiança 0,5); início do beat grid em 0,362667 s. Downbeat/fase de compassos e rótulos de seção requerem escuta. O mapa contém beat grid, compassos hipotéticos, atividade, entradas, onsets por role, frases, densidade e transições com confiança. Não houve hardcode do BPM nem uso dos timestamps externos como entradas da detecção.

Transições detectadas por mudanças de energia/densidade em contexto de 2 s: **22.3, 53.6, 115.1, 134.2, 179.8, 219.7, 233.1, 242.0 s**. Essa segmentação inicial cria nove seções de textura; os nomes formais não estão confirmados. O mapa também compara separadamente os candidatos externos. 35 s e 205,5 s não foram escolhidos entre as oito maiores novidades; não foram forçados como limites.

## Brass e Other

Brass tem aproximadamente **21.47 s** de atividade acima de −60 dBFS (**8.7%** da música). Concentra frases em 119–134 s e 198–222 s, com uma entrada curta perto de 178,4 s. Uma atividade final de cerca de 48 ms também foi registrada como metadado. A hipótese de função é acento/resposta episódica, ainda sujeita à avaliação musical. Em 200–230 s, sua atividade ocupa 40% do intervalo.

Other apresenta energia principalmente baixa/média, com centroide mediano aproximado de 1.087 Hz. Esses descritores não identificam seu instrumento. A classificação permanece pendente; foi fornecida uma audição isolada e usada uma posição fixa conservadora, sem trajetórias específicas de conteúdo.

## Gain staging e seleção do preview

Soma alinhada em unity gain, medida em float64 somente como diagnóstico: **+5.20 dBFS**. Atenuação comum pré-dearVR: **-27.33 dB**, calculada pela soma dos picos individuais para assegurar margem conservadora de −12 dBFS no pior caso dry. Ganhos por role são não positivos. Um ganho comum transparente após a renderização coloca o maior pico das comparações em −6 dBFS. Para matching, somente o dry recebeu atenuação adicional de 0,5 dB; não há limiter escondendo soma.

200–230 s cobre os 11 roles e mais Brass que o melhor candidato de score, 213–243 s. Seu score está a menos de 1% do melhor intervalo computado. O trecho contém frases de Brass, desenvolvimento de woodwinds e a transição forte de 219,7 s. A participação significa atividade em algum momento do intervalo, não os 11 stems continuamente simultâneos.

## Cena explicável

| Role | Decisão |
|---|---|
| lead_vocal | Centro frontal estável; protege clareza e inteligibilidade. |
| backing_vocals | Camada traseira esquerda; separa respostas da voz principal sem alterar Stereo Width. |
| woodwinds | Frases longas atravessam o campo traseiro para destacar respostas expressivas; entradas curtas ficam localizadas. |
| drums | 8° à frente, estável; âncora de impacto e ritmo. |
| bass | Centro baixo estável; âncora de graves. |
| guitar | Faixa esquerda, com deslocamentos discretos nas mudanças de textura. |
| keyboards | Faixa direita elevada; complementa Guitar sem copiar a cena Tukãna. |
| percussion | Uma única órbita de oito compassos hipotéticos, culminando no relaxamento de textura perto de 219,7 s; permanece fixa antes e depois. |
| synth | Camada sustentada superior/traseira direita; mudanças discretas conforme seção. |
| other | −18°, elevação 0°, ganho −4 dB; fixo e conservador enquanto sua identidade é investigada. |
| brass | Posição estável por frase, alternando lados nas pausas; nenhum movimento contínuo de efeito. |

Cada keyframe tem justificativa e usa tempo absoluto da música. A cena é independente do renderer. DearVR PRO 2 usa uma instância por stem, distância efetiva fixa de 3 m, reflexão/reverb desativados conforme T017 e nenhuma automação experimental T018.

## Validação e regressões

- 15 WAVs de entrega: hashes, PCM24, 48 kHz, estéreo e duração exata confirmados.
- Os 11 stems usam o mesmo frame inicial 9.600.000. Pre-roll uniforme de 1 s aquece as instâncias; a mesma remoção de pre-roll preserva o intervalo de todos os stems. Não há trimming por atividade.
- Sem NaN/Inf ou clipping. Continuidade medida nas fronteiras reais do plugin, com fase de 128 frames após o pre-roll; nenhum outlier pelo critério herdado da baseline.
- Órbita da percussão: 80° → 440° (360°), uma passagem pelo wrapping ±180°, maior passo circular aproximado de 0,108° por bloco.
- Os diagnósticos de transientes usam envelopes de magnitude de 5 ms e busca de lag ±100 ms; os 50 eventos fortes de cada role medido continuam presentes. A qualidade perceptiva dos transientes não é inferida somente dessa medição.
- Binaural: correlação L/R 0,724; redução RMS em mono cerca de 0,644 dB. Dry: correlação 0,928. A adequação musical continua dependente da escuta.
- Importer legado reproduz exatamente o manifesto Tukãna de dez roles. Casos de três e onze roles passaram; aliases Brass, Keyboard e Lead Vocals foram exercitados.
- Testes de PCM16/24/32, float32, mono/estéreo, corrupção e resampling temporal passaram. Nenhum resampling foi necessário na MUSIC 02.
- Adapter, analyzer, composer, renderers e mastering aprovados permanecem idênticos à tag T017; wrapping, distância fixa e interpolação de ganho foram exercitados. Nenhum import T018 ativo.
- Todos os arquivos do projeto Tukãna foram comparados por SHA-256, tamanho e mtime antes/depois: intactos. B2 mantém seu hash oficial.

Não foi repetido um render integral de Tukãna nesta etapa: seu DSP permanece byte a byte igual à baseline já validada integralmente. A mudança compartilhada é restrita aos aliases e à configuração de roles do importer, cuja compatibilidade foi testada diretamente.

## Evidências e comandos

- [Manifesto e hashes](../analysis/stem_import_manifest.json)
- [Musical map](../analysis/musical_map.json)
- [Brass](../analysis/brass_analysis.json)
- [Other](../analysis/other_content_analysis.json)
- [Cena inicial](../spatial_scenes/M02_T001_initial_scene.json)
- [Validação do preview](M02_T001_preview_validation.json)
- [Validação dos WAVs exportados](M02_T001_encoded_artifacts_validation.json)
- [Stems espacializados](../spatial_stems/M02_T001_preview_200_230/)

Comandos: `python backend/spatial/music02_analysis.py`, `python backend/spatial/music02_preview.py` e `python backend/tests/test_m02_t001_preview.py`, usando o Python de `.venv`. Os scripts escrevem exclusivamente no projeto MUSIC 02; uma nova execução regenerará seu protótipo.

Aguardar avaliação humana do binaural contra o dry: proximidade, voz, bateria, Brass, naturalidade e intenção do movimento. Other deve ser identificado antes de uma decisão espacial definitiva. **Não renderizar a música completa nem masterizar antes dessa avaliação.**
