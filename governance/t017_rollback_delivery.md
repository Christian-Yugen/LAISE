# Retorno oficial à T017 — 11/10/2026

## Auditoria e rollback

HEAD inicial: 8ce8268. Não havia commits T018 identificáveis; o trabalho
T012–T018 estava no working tree. Nenhum reset global foi feito.
O inventário prévio está em t018_rollback_inventory.md.

Os módulos t018_acoustic_depth.py e t0181_proximal_depth.py implementavam
distância dinâmica/compensação, microdistância, early reflections e Clarity
em renders experimentais independentes. Seus dois testes eram pontos de
execução desses experimentos. Os quatro arquivos foram retirados do backend
e arquivados em evidence/EXPERIMENTAL_REJECTED/t018; testes terminam em .py.txt.
Os relatórios e renders T018/T018.1 foram preservados como evidência rejeitada,
registrados no manifesto, com marcadores nos diretórios de renders.

Nenhum trecho DSP T018 foi encontrado nos arquivos compartilhados do pipeline.
As correções anteriores do dearVR adapter — órbita desembrulhada, offsets de
timeline e automação de ganho — foram preservadas. A distância continua fixa
em 3 m / raw 0.0969899744. Auditoria AST: 104 arquivos ativos válidos, sem
imports T018. Acrescentada recusa de sobrescrita de uma B2 já existente.

## Validação

Comando: .venv/Scripts/python.exe backend/tests/validate_t017_baseline.py

- T015 PASS: render integral dos dez stems; hashes dos dez stems e dos mixes
  binaural/seco idênticos aos aprovados; sincronização e frames preservados.
- T016 PASS: todos os onze critérios objetivos de mastering passaram.
- T017 PASS: todos os doze critérios objetivos passaram; B2 reproduzida com
  o hash oficial em projeto isolado.
- Composer recompõe exatamente a cena aprovada. dearVR real validado em
  poses/órbitas; distância fixa e interpolação de keyframes/ganho confirmadas.
- B2 original intacta: 24-bit, 48 kHz, estéreo, 12.844.801 frames,
  267,60002083333336 s; conteúdo, tamanho e mtime preservados.

SHA-256 confirmado:
9daf544d7e073d8791f6260eed2630863a9280a2cca7d22053132a881e2c0df9

Evidência detalhada: t017_baseline_validation.json. Saídas de regressão ficam
em projects/_baseline_validation, ignoradas pelo Git e fora da produção.
Áudio e plugin proprietário continuam locais; a tag versiona código, cenas,
configurações, evidências e hashes, não os WAVs ou o binário dearVR.

## Próxima música

O método aprovado está disponível, sem lógica T018 ativa. Seguir
t017_method_for_new_music.md: importar/analisar a música nova, definir decisões
espaciais próprias e validar antes de aprovar mastering. Os wrappers Tukana
têm duração específica; uma nova música exige usar seus próprios frames e
caminhos, preservando a timeline. Nenhum processamento novo foi iniciado.
