# LAISE Visualizer V1.3C — Relatório de evolução visual R8A

Data: 23/10/2026. Escopo: implementação e refinamento da luz em três amostragens, incluindo arquivos alterados, melhorias e evidências técnicas.

O resultado atual combina emissão neon seletiva, iluminação mais contínua nas encostas e um acabamento óptico suave. Música, física, geometria, câmera e controles foram preservados. As mudanças estão em um worktree separado; ainda não foram integradas à branch musical.

`TECHNICAL_STATUS=PASS` · `VISUAL_STATUS=PENDING_HUMAN_REVIEW`

[Comparação das amostragens](http://127.0.0.1:5174/reports/v1_3c-r8a-hdr-neon-emission/review.html) · [Aplicação ao vivo](http://127.0.0.1:5174/behavior-lab-v13c.html)

## 1. Ponto de partida

A referência usada foi a imagem enviada pelo usuário, “Terreno Reativo Neon em Onda (1).png”: ouro central luminoso, magenta/violeta e ciano/azul, cristas muito claras, halos suaves e áreas escuras legíveis.

O renderer aprovado já tinha suporte HDR, saída sRGB, tone mapping Reinhard, exposição 1,15 e bloom. O diagnóstico não identificou necessidade de reconstruir esse pipeline nem erro de dupla conversão de cores. A principal oportunidade era distribuir melhor a emissão luminosa sobre o relevo existente.

A base foi o checkpoint aprovado `2538e6e90b6fb7d27aa59b1a1ee0394e1069c91b`. O motor musical R2 em desenvolvimento no diretório original foi preservado e não foi incorporado ao experimento visual.

## 2. Como o trabalho evoluiu

| Etapa | O que mudou | Melhoria e observação |
|---|---|---|
| Primeira amostragem — emissão HDR | Descritor de curvatura local, emissão adicional nas linhas, seleção por orientação e inclinação, núcleos quase brancos e ajuste do bloom existente | Aumentou a luminosidade seletiva e tornou os destaques mais presentes. O usuário gostou, mas observou focos separados em uma mesma encosta. |
| Segunda amostragem — continuidade | Separação entre luz colorida contínua da encosta e acento de crista; filtro espacial dos descritores; redução da concentração dos realces; maior participação da superfície | Redistribuiu a luz, dando mais continuidade à leitura das faces. O usuário relatou gostar muito dessa versão e pediu um efeito luminoso adicional. |
| Terceira amostragem — acabamento óptico | Aura suave e prolongamentos horizontais seletivos no bloom existente, com fonte filtrada e seleção suave das concentrações luminosas | Acrescentou espalhamento óptico ao brilho já existente. A avaliação estética dessa nova contribuição permanece pendente. |

### Primeira amostragem

Foi criado um descritor que identifica curvaturas convexas a partir das posições reais da malha já deformada. O cálculo descreve o relevo; não altera os vértices nem as forças que formam a onda.

A emissão passou a considerar orientação à luz principal, inclinação e curvatura. As regiões mais intensas podem se aproximar do branco, com um tom levemente quente no ouro central. A paleta R7C continuou sendo a base cromática.

O bloom existente foi reutilizado. Sua intensidade base passou de 0,14 para 0,18 e o limiar de luminosidade de 1,1 para 2,0; a exposição permaneceu em 1,15. Não foram acrescentados passes ou luzes.

### Segunda amostragem

Após a observação dos focos isolados, a contribuição contínua da encosta passou a ter controle separado do destaque de crista. A emissão adicional da superfície passou de 0,012 para 0,035 da contribuição calculada, preservando a predominância das linhas.

Foi aplicado um filtro espacial binomial 3 × 3 somente aos descritores auxiliares de brilho: curvatura e direção usada pela emissão. A curvatura mantém o sinal durante a filtragem, evitando transformar pequenas alternâncias entre vértices em manchas luminosas.

As normais geométricas originais continuam intactas e ainda controlam a fronteira entre luz e sombra. O filtro não suaviza a forma das ondas e não introduz atraso temporal.

A altura continua sendo um dos fatores do mecanismo anterior. Ela não determina sozinha o brilho: uma ondulação baixa voltada à luz pode ser mais luminosa que uma montanha alta orientada para o lado oposto.

### Terceira amostragem

O novo acabamento funciona sobre a imagem HDR já produzida pela cena. Reutiliza as texturas do bloom para acrescentar uma aura pequena e prolongamentos horizontais nas concentrações mais intensas de luminosidade.

Durante a calibração foram identificados dois problemas: prolongar toda a face criava faixas largas; uma seleção muito estreita e uma amostragem pouco densa repetiam contornos no halo. A versão final usa uma fonte previamente filtrada, uma seleção suave de concentrações verticais de luminosidade e amostragem horizontal mais densa.

Não existe uma nova luz viajando pela montanha. O efeito acompanha a mudança de brilho das ondas já existentes. Não foi criado oscilador, relógio de pulsação ou novo movimento musical.

## 3. Arquivos da aplicação

Todos os caminhos abaixo são relativos a `C:\Projetos2026\LAISE\.worktrees\r8a-hdr\visualizer`.

| Arquivo | Estado | Responsabilidade |
|---|---|---|
| `src/behavior-lab-v13c.js` | Modificado | Integração dos descritores, shaders emissivos e acabamento óptico ao renderer existente. |
| `src/neon-emission-r8a.js` | Novo | Parâmetros da emissão, cálculos auxiliares de curvatura/direção e shader que separa a luz da encosta dos destaques. Evoluiu da primeira para a segunda amostragem; permaneceu idêntico na terceira. |
| `src/neon-optics-r8a.js` | Novo | Aura e prolongamentos horizontais seletivos, integrados à composição do bloom existente e ao redimensionamento da janela. |

Em relação ao checkpoint aprovado, o diff do arquivo já rastreado `behavior-lab-v13c.js` contém 41 linhas acrescentadas e 9 removidas. Os dois módulos novos são apresentados separadamente no patch completo.

Na terceira etapa, o renderer recebeu apenas um import e uma chamada de integração do efeito óptico. A emissão e o sombreamento da segunda amostragem foram preservados.

## 4. Ferramentas e materiais de revisão

| Arquivo | Finalidade |
|---|---|
| `tools/prepare_r8a_fields.mjs` | Gerar estados físicos determinísticos do motor aprovado para comparação. |
| `tools/capture_r8a.py` | Capturar o renderer real e comparar hashes de geometria, câmera e cores. |
| `tools/validate_r8a.mjs` | Conferir arquivos protegidos, limites do diff e integridade dos descritores visuais. |
| `tools/measure_r8a.py` | Medir luminância, pixels quase brancos e clipping simultâneo dos três canais. |
| `tools/validate_neon_optics_r8a.py` | Verificar efeito desligado, redimensionamento e reprodução ao vivo com WebGL. |

O diretório `reports/v1_3c-r8a-hdr-neon-emission` reúne:

- `baseline`: referência anterior à R8A e hashes dos arquivos protegidos.
- `first-sample` e `second-sample`: códigos, capturas e resultados preservados das entregas anteriores.
- `r8a`: capturas da terceira amostragem atual.
- `review.html`: comparação interativa com seleção do instante e da amostragem anterior.
- `README.md`, `refinement.md` e `optics.md`: documentação geral e de cada refinamento.
- `changes.patch`: diff completo da aplicação em relação à base aprovada.
- `refinement.patch`: evolução da primeira para a segunda amostragem.
- `optics.patch`: evolução da segunda para a terceira amostragem.
- `capture-validation.json`, `contract-validation.json`, `optics-validation.json`, `image-measurements.json`, `review-page-validation.json` e `final-validation.json`: evidências e estados técnicos.
- `fields` e `build`: dados de comparação e resultado do build de validação.

Essas ferramentas e evidências não acrescentam controles à interface do visualizador.

## 5. Configuração atual

| Parâmetro | Valor |
|---|---:|
| Intensidade geral da emissão | 4,8 |
| Contribuição contínua da encosta | 1,25 |
| Contribuição do destaque de crista | 2,2 |
| Limiar de curvatura | 4,5 |
| Suavidade da seleção de curvatura | 3,0 |
| Aquecimento do núcleo dourado | 0,28 |
| Bloom base | 0,18 |
| Limiar HDR do bloom | 2,0 |
| Exposição | 1,15 |
| Fração da nova emissão aplicada à superfície | 0,035 |
| Intensidade da aura óptica | 0,08 |
| Ganho do prolongamento óptico | 1,20 |
| Limiar na fonte óptica filtrada | 1,20 |
| Alcance óptico relativo à altura da janela | 0,085 |

O limiar da fonte óptica filtrada e o limiar HDR do bloom operam em etapas distintas; seus valores não são diretamente comparáveis.

## 6. O que foi preservado

Permaneceram intactos os arquivos e cálculos musicais protegidos: ataques, gestos, forças, posições T007, R3.2/R4, Open Boundary R5, composição vertical e footprint R6.4, runtime e áudio.

Também foram preservados a malha de 129 × 129 vértices, dimensões, posições, índices, normais geométricas, câmera, enquadramento, paleta R7C, ouro central, HTML, CSS, HUD, timeline e controles.

A composição continua usando `RenderPass`, `UnrealBloomPass` e `OutputPass`. O efeito óptico reutiliza o material e os buffers do bloom; não cria novas malhas, luzes, materiais ou passes. O sombreamento direcional anterior permanece no código. A dispersão óptica pode se sobrepor visualmente a regiões escuras, por isso o balanço percebido ainda depende de revisão humana.

Piso refletivo, reflexos, feixes volumétricos e rotação automática de câmera continuam fora desta implementação.

## 7. Verificações e resultados

| Verificação | Resultado e alcance |
|---|---|
| Sintaxe e build da entrada V1.3C | PASS. Build com aviso de bundle acima de 500 kB, sem falha. |
| Arquivos protegidos do diretório musical original | 24 arquivos com hashes preservados. |
| Arquivos protegidos do worktree | 20 arquivos existentes permaneceram idênticos; o renderer é a exceção de apresentação prevista. |
| Comparação de estados físicos | Posições, índices, normais, cores, campo de entrada, câmera e pose idênticos entre as amostragens nos quatro instantes. |
| Shaders e WebGL | Sem erros registrados nas capturas e na reprodução testada. |
| Efeito óptico desligado | Diferença RGB máxima zero contra a segunda amostragem em 03:20. |
| Redimensionamento | PASS em 1280 × 720 e 390 × 844; proporção do efeito e três passes mantidos. |
| Reprodução ao vivo | Play, seek para 03:16 e pause após 03:18 passaram sem erro de áudio, JavaScript ou WebGL. |
| Comparação interativa | Quatro instantes, três referências anteriores, slider e largura móvel verificados. |

As capturas reais foram feitas em 01:05, 01:10, 01:15 e 03:20, na resolução de 1920 × 919. O campo físico e a atmosfera foram fixados para isolar a apresentação. Texto e HUD foram ocultados somente nas capturas de comparação devido a artefatos de composição do Chrome de teste; o aplicativo ao vivo conserva sua interface.

Na máscara de pixels cromáticos definida pelo baseline, a primeira amostragem tinha aproximadamente 0,24% a 0,99% de pixels quase brancos. Na versão atual, o intervalo é aproximadamente 0,13% a 0,66%. Não foram encontrados pixels com os três canais simultaneamente ≥254 nessa máscara. Esses números não excluem saturação de canais individuais nem comprovam qualidade estética.

Não foram repetidas as baterias históricas do motor musical. A validação cobriu o escopo visual alterado; não constitui uma avaliação de desempenho em diferentes GPUs ou de toda a animação possível.

## 8. Estado de entrega

Branch: `feature/visualizer-v1.3c-r8a-hdr-neon-emission`.

Worktree: `C:\Projetos2026\LAISE\.worktrees\r8a-hdr`.

HEAD permanece em `2538e6e90b6fb7d27aa59b1a1ee0394e1069c91b`. Os arquivos alterados e novos ainda não estão commitados. Nenhum merge, PR ou tag foi realizado.

As duas primeiras amostragens receberam comentários positivos do usuário. O estado formal de aceitação estética continua `PENDING_HUMAN_REVIEW`, incluindo o novo acabamento óptico. A melhoria técnica está implementada e verificável; a semelhança com a referência e a sensação de beleza ou hipnotismo dependem da avaliação humana.
