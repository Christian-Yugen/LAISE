# M02-T004 — Object Separation & Near-Field Presence

Testes isolados, análise por seção e preview 200–230 s concluídos. Validação técnica **PASS**; avaliação perceptiva **PENDENTE**.

## Avaliação humana T003 registrada

Direcionalidade básica e 3D: **PASS**. Separação simultânea: **PARCIAL**. Near-field extremo: **INSUFICIENTE**. Oito direções, frente/trás, alturas e movimento circular foram percebidos. Quatro fontes ainda se confundem sobretudo em esquerda/direita; o áudio permanece natural, com espaço para clareza. A superioridade da T003 não foi estabelecida. **T003 não foi promovida.**

## 1. Aproximação — mesma fonte, três políticas

Ouça em fones, mantendo o volume confortável e fixo entre variantes. A direção permanece +80°, na altura do ouvido. O mesmo trecho de um stem original é repetido em todas as variantes. A montagem tem 24 s e fades de 20 ms nas bordas de cada repetição.

- [A — compensação total](monitors/near_field_total_24s_24bit.wav)
- [B — compensação parcial, até +2,5 dB](monitors/near_field_partial_24s_24bit.wav)
- [C — crescimento natural limitado a +4,5 dB](monitors/near_field_natural_limited_24s_24bit.wav)

Controles estáticos level-matched para comparar timbre e localização sem crescimento de nível:

- [0.25 m — mesmo som](diagnostics/distance/0.25_level_matched_24bit.wav)
- [0.35 m — mesmo som](diagnostics/distance/0.35_level_matched_24bit.wav)
- [0.5 m — mesmo som](diagnostics/distance/0.5_level_matched_24bit.wav)
- [0.75 m — mesmo som](diagnostics/distance/0.75_level_matched_24bit.wav)
- [1 m — mesmo som](diagnostics/distance/1.0_level_matched_24bit.wav)
- [1.5 m — mesmo som](diagnostics/distance/1.5_level_matched_24bit.wav)

| Tempo | Distância nominal |
|---|---:|
| 0 s | 1.5 m |
| 3 s | 1 m |
| 6 s | 0.75 m |
| 9 s | 0.5 m |
| 12 s | 0.35 m |
| 15 s | 0.25 m |
| 18 s | 0.5 m |
| 21 s | 1 m |
| 24 s | 1.5 m |

Entre pontos, o controle de distância e o ganho evoluem continuamente. Não foi usado 0,1 m. As três variantes usam o mesmo ganho geral de segurança; **não** recebem matching de loudness entre políticas, pois isso apagaria o crescimento em teste. A curva de compensação foi medida no próprio som e direção. O crescimento é limitado por ganho vinculado suave, sem limiter.

Perguntas: passou perto do ouvido? Pareceu fisicamente próximo ou apenas mais alto? Mudou o timbre? A direção permaneceu clara? Ficou dentro ou fora da cabeça? Algum trecho ficou artificial ou desconfortável?

Após remover o ganho por ajuste escalar, o residual entre 0,25 e 1,5 m foi -47.4 dB relativo ao sinal. Neste probe o controle é predominantemente de nível. Isso limita a hipótese de produzir proximidade física apenas com o parâmetro de distância; não se confundiu crescimento de volume com near-field comprovado.

O controle em metros é nominal; o display arredonda a 0,1 m. A medição RMS não garante loudness perceptiva equivalente nem externalização.

## 2. Objetos — isolados, pares, quatro

[Monitor de posições — 22,5 s](monitors/objects_sequence_pairs_four_22_5s_24bit.wav)

A: frente-esquerda / ouvido. B: frente-direita / elevado. C: trás-esquerda / elevado. D: trás-direita / ouvido. Todos a 1 m, com exatamente o mesmo som.

| Trecho | Tempo |
|---|---|
| A | 0–2 s |
| B | 2.5–4.5 s |
| C | 5–7 s |
| D | 7.5–9.5 s |
| A+B | 10–12 s |
| A+C | 12.5–14.5 s |
| B+D | 15–17 s |
| C+D | 17.5–19.5 s |
| A+B+C+D | 20–22 s |

Há 0,5 s de pausa após cada trecho. Registre em qual etapa duas posições deixam de ser distinguíveis. Não é necessário nomear instrumentos.

Limite do teste solicitado: cópias idênticas e sincronizadas são correlacionadas e podem fundir em uma imagem fantasma. A perda de separação neste monitor não demonstra, sozinha, incapacidade de separar fontes musicais independentes. O ganho por contagem 1/√N evita aumento mecânico, mas não iguala perfeitamente somas coerentes.

## 3. Compactness — controles reversíveis

Tratamento somente antes do dearVR: M/S com ganho RMS vinculado. A = original; B = Side ×0,65; C = Side ×0,35, somente quando a triagem detecta Side >30% da energia M/S ou correlação L/R <0,30. Não se alterou Stereo Width do plugin.

### percussion

Trecho 222.00–230.00 s; Side 5.5% da energia M/S; correlação 0.893.

- [A_original](diagnostics/compactness/percussion/A_original_level_matched_24bit.wav)
- [B_side65](diagnostics/compactness/percussion/B_side65_level_matched_24bit.wav)

Avalie localização, riqueza estéreo, naturalidade e eventual perda de conteúdo. Maior compactness medida não prova melhor localização.

### woodwinds

Trecho 218.40–226.40 s; Side 6.4% da energia M/S; correlação 0.877.

- [A_original](diagnostics/compactness/woodwinds/A_original_level_matched_24bit.wav)
- [B_side65](diagnostics/compactness/woodwinds/B_side65_level_matched_24bit.wav)

Avalie localização, riqueza estéreo, naturalidade e eventual perda de conteúdo. Maior compactness medida não prova melhor localização.

### brass

Trecho 213.90–221.90 s; Side 2.0% da energia M/S; correlação 0.962.

- [A_original](diagnostics/compactness/brass/A_original_level_matched_24bit.wav)
- [B_side65](diagnostics/compactness/brass/B_side65_level_matched_24bit.wav)

Avalie localização, riqueza estéreo, naturalidade e eventual perda de conteúdo. Maior compactness medida não prova melhor localização.

### backing_vocals

Trecho 205.40–213.40 s; Side 22.6% da energia M/S; correlação 0.548.

- [A_original](diagnostics/compactness/backing_vocals/A_original_level_matched_24bit.wav)
- [B_side65](diagnostics/compactness/backing_vocals/B_side65_level_matched_24bit.wav)

Avalie localização, riqueza estéreo, naturalidade e eventual perda de conteúdo. Maior compactness medida não prova melhor localização.

Nenhum dos quatro stems atingiu o critério de inclusão da variante C neste trecho. A música conserva o candidato anterior de Lead/Percussion com Side ×0,5; os novos testes não foram adotados como se tivessem aprovação humana. Woodwinds, Brass, Backing e Synth permanecem com largura original no preview.

## 4. Masking, clareza e turn-taking

A análise usa STFT Hann 4096 / hop 2048, potência dos dois canais e seis bandas entre 60 Hz e 20 kHz. Analisa separadamente os trechos 200–207,02; 207,05–218,50; 218,71–224,43; 224,50–230 s. A auditoria temporal usa RMS a cada 100 ms, coatividade e correlação dos envelopes. Sobreposição espectral e atividade indicam competição potencial, não um limiar psicoacústico comprovado.

| Seção | Objeto em destaque | Ajustes de suporte |
|---|---|---|
| 200.00–207.02 s | woodwinds | backing_vocals: -2 dB, synth: -2 dB |
| 207.05–218.50 s | percussion | guitar: -2 dB, other: -1.5 dB, brass: -2 dB |
| 218.71–224.43 s | woodwinds | synth: -2 dB |
| 224.50–230.00 s | Posições estáveis | Nenhum indicado pelo critério |

O critério combina sobreposição de bandas >0,75 e RMS relativo >−8 dB. Reduções de suporte são pequenas e usam rampas de 250 ms; Lead, Drums e Bass não recebem esses cortes. Não há EQ global ou corretivo. O detalhe das bandas/potenciais competidores está no relatório de masking.

O relatório também inclui análise somente de leitura das 9 seções do mapa T001, com pares de possível competição espectral/temporal. O mapa estrutural é provisório, não foi validado musicalmente fora do preview, e nenhum ajuste ou render completo foi produzido para essas seções.

Woodwinds se move durante suas duas frases. Percussion executa uma volta de 360° entre elas (207,05–218,50 s), com breves retenções nos setores. Backing e Synth mantêm suas regiões. Brass alterna lados no intervalo silencioso entre as duas entradas e permanece localizado durante as frases. A auditoria registra o número máximo de objetos expressivos angulares ativos: **1**.

Eventos selecionados: Woodwinds aproxima a 0,35 m em 203,15 s; Percussion aproxima a 0,25 m em 210,50 s. A cena musical usa a política parcial, preservando até 2,5 dB adicionais de crescimento calibrado relativamente à casa de cada fonte, sem normalizar cada evento posteriormente. Fora desses eventos, o crescimento adicional é zero.

A comparação na pasta final_comparison é a entrega para escuta. Os primeiros exports internos T004 foram preservados como intermediários anteriores à revisão da referência de ganho; não são recomendações de escuta. A revisão usa ganho vinculado após o plugin e mantém poses/distâncias, sem EQ ou limiter. A aproximação numérica devido ao PCM24 anterior é inferior a um LSB e está documentada.

## 5. Preview e comparação T003/T004

- [T003_200_230 — 200–230 s](renders/final_comparison/T003_200_230_level_matched_24bit.wav)
- [T004_200_230 — 200–230 s](renders/final_comparison/T004_200_230_level_matched_24bit.wav)

| Versão | LUFS | True peak |
|---|---:|---:|
| T003_200_230 | -22.9 | -8.4 dBTP |
| T004_200_230 | -22.9 | -6.9 dBTP |

Matching usa somente ganho vinculado constante por versão. O crescimento local de aproximação dentro da T004 é preservado. Todos os previews têm 30 s, PCM24, 48 kHz, estereo e 1.440.000 frames, com pre-roll comum de 1 s. Nenhum trimming por atividade.

## Spatial homes

| Role | Azimute | Elevação | Distância |
|---|---:|---:|---:|
| lead_vocal | 0° | 0° | 1.1 m |
| backing_vocals | -115° | 18° | 0.9 m |
| woodwinds | -78° | 28° | 1.1 m |
| drums | 22° | -18° | 1.2 m |
| bass | 0° | -42° | 1.3 m |
| guitar | -48° | 0° | 1.25 m |
| keyboards | 50° | 30° | 1.3 m |
| percussion | 85° | -12° | 0.9 m |
| synth | 155° | 55° | 1.5 m |
| other | -165° | -8° | 1.6 m |
| brass | 125° | -32° | 1 m |

As âncoras centrais permanecem fixas; Guitar e Keyboard ocupam lados frontais opostos com alturas diferentes. As casas dos objetos móveis são referências, com exceções por frase documentadas. Other mantém ganho conservador e identidade pendente.

## Relatórios e regressões

Verificados 66 WAVs e todos os 228 arquivos MUSIC 02 anteriores e 79 arquivos Tukãna por SHA-256, tamanho e mtime. Baseline T017 e DSP aprovado preservados. Testes de ganho/distância, frames, sequência de objetos, turn-taking, continuidade de blocos e comparação passaram.

- [Relatório técnico](reports/M02_T004_validation.json)
- [Compactness](reports/compactness.json)
- [Masking/clareza](reports/masking_clarity.json)
- [Near-field e calibração](reports/near_field.json)
- [Monitor de objetos](reports/object_monitor.json)
- [Auditoria angular](reports/angular_separation.json)
- [Cena](spatial_scenes/M02_T004_scene.json)
- [Ganho dos eventos relativo às casas](reports/event_gain_reference.json)
- [Regressões](reports/M02_T004_encoded_regression.json)
- [Avaliação humana T003](reports/M02_T003_human_review.json)
- [Pedido original e avaliação recebida](reports/M02_T004_user_request.md)

## Avaliação humana acessível

Sem exigir nomes: o som veio da frente? Veio de trás? Pareceu acima? Passou perto do ouvido? Você percebeu duas fontes em lugares diferentes? Algum som pareceu circular? A cena ficou mais clara? Algum som ficou artificial? Qual política de aproximação funcionou melhor e com conforto?

Critérios perceptivos permanecem pendentes: localização de objetos, proximidade física extrema, timbre, externalização, naturalidade e conforto. Coordenadas e ausência de clipping não provam sucesso auditivo.

**T001, T002, T003 e Tukãna preservadas. Nenhuma promoção, masterização ou música completa renderizada. Aguardar avaliação humana antes de prosseguir.**
