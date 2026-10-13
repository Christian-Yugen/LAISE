"""Human-accessible T004 listening index, written after render and regressions."""
from pathlib import Path
from music02_t004 import OUT,load

def link(label,path):return f'[{label}]({Path(path).relative_to(OUT).as_posix()})'

def run():
    r=load(OUT/'reports/M02_T004_validation.json');tests=load(OUT/'reports/M02_T004_encoded_regression.json')
    assert r['technical_status']==tests['status']=='PASS'
    scene=load(OUT/'spatial_scenes/M02_T004_scene.json')
    lines=['# M02-T004 — Object Separation & Near-Field Presence','',
        'Testes isolados, análise por seção e preview 200–230 s concluídos. Validação técnica **PASS**; avaliação perceptiva **PENDENTE**.',
        '', '## Avaliação humana T003 registrada','',
        'Direcionalidade básica e 3D: **PASS**. Separação simultânea: **PARCIAL**. Near-field extremo: **INSUFICIENTE**. Oito direções, frente/trás, alturas e movimento circular foram percebidos. Quatro fontes ainda se confundem sobretudo em esquerda/direita; o áudio permanece natural, com espaço para clareza. A superioridade da T003 não foi estabelecida. **T003 não foi promovida.**','',
        '## 1. Aproximação — mesma fonte, três políticas','',
        'Ouça em fones, mantendo o volume confortável e fixo entre variantes. A direção permanece +80°, na altura do ouvido. O mesmo trecho de um stem original é repetido em todas as variantes. A montagem tem 24 s e fades de 20 ms nas bordas de cada repetição.','']
    names={'total':'A — compensação total','partial':'B — compensação parcial, até +2,5 dB','natural_limited':'C — crescimento natural limitado a +4,5 dB'}
    for policy,entry in r['near_field']['exports'].items():lines.append('- '+link(names[policy],entry['path']))
    lines += ['', 'Controles estáticos level-matched para comparar timbre e localização sem crescimento de nível:','']
    for record in r['near_field']['calibration']:lines.append('- '+link(f"{record['distance_m']:g} m — mesmo som",record['export']['path']))
    lines += ['', '| Tempo | Distância nominal |','|---|---:|']
    for point in r['near_field']['monitor_trajectory']:lines.append(f"| {point['time_seconds']:g} s | {point['distance_m']:g} m |")
    lines += ['', 'Entre pontos, o controle de distância e o ganho evoluem continuamente. Não foi usado 0,1 m. As três variantes usam o mesmo ganho geral de segurança; **não** recebem matching de loudness entre políticas, pois isso apagaria o crescimento em teste. A curva de compensação foi medida no próprio som e direção. O crescimento é limitado por ganho vinculado suave, sem limiter.',
        '', 'Perguntas: passou perto do ouvido? Pareceu fisicamente próximo ou apenas mais alto? Mudou o timbre? A direção permaneceu clara? Ficou dentro ou fora da cabeça? Algum trecho ficou artificial ou desconfortável?',
        '', f"Após remover o ganho por ajuste escalar, o residual entre 0,25 e 1,5 m foi {r['near_field']['calibration'][0]['normalized_waveform_residual_vs_1_5m_db']:.1f} dB relativo ao sinal. Neste probe o controle é predominantemente de nível. Isso limita a hipótese de produzir proximidade física apenas com o parâmetro de distância; não se confundiu crescimento de volume com near-field comprovado.",
        '', 'O controle em metros é nominal; o display arredonda a 0,1 m. A medição RMS não garante loudness perceptiva equivalente nem externalização.',
        '', '## 2. Objetos — isolados, pares, quatro','',link('Monitor de posições — 22,5 s',r['objects']['export']['path']),
        '', 'A: frente-esquerda / ouvido. B: frente-direita / elevado. C: trás-esquerda / elevado. D: trás-direita / ouvido. Todos a 1 m, com exatamente o mesmo som.','',
        '| Trecho | Tempo |','|---|---|']
    for cue in r['objects']['schedule']:lines.append(f"| {cue['cue']} | {cue['start_seconds']:g}–{cue['end_seconds']:g} s |")
    lines += ['', 'Há 0,5 s de pausa após cada trecho. Registre em qual etapa duas posições deixam de ser distinguíveis. Não é necessário nomear instrumentos.',
        '', 'Limite do teste solicitado: cópias idênticas e sincronizadas são correlacionadas e podem fundir em uma imagem fantasma. A perda de separação neste monitor não demonstra, sozinha, incapacidade de separar fontes musicais independentes. O ganho por contagem 1/√N evita aumento mecânico, mas não iguala perfeitamente somas coerentes.',
        '', '## 3. Compactness — controles reversíveis','',
        'Tratamento somente antes do dearVR: M/S com ganho RMS vinculado. A = original; B = Side ×0,65; C = Side ×0,35, somente quando a triagem detecta Side >30% da energia M/S ou correlação L/R <0,30. Não se alterou Stereo Width do plugin.','']
    for role,diagnostic in r['compactness'].items():
        im=diagnostic['original_image'];lines += [f"### {role}",'',f"Trecho {diagnostic['interval'][0]:.2f}–{diagnostic['interval'][1]:.2f} s; Side {100*im['effective_width_side_over_total_energy']:.1f}% da energia M/S; correlação {im['correlation']:.3f}.",'']
        for label,e in diagnostic['exports']['matched'].items():lines.append('- '+link(label,e['path']))
        lines += ['', 'Avalie localização, riqueza estéreo, naturalidade e eventual perda de conteúdo. Maior compactness medida não prova melhor localização.','']
    lines += ['Nenhum dos quatro stems atingiu o critério de inclusão da variante C neste trecho. A música conserva o candidato anterior de Lead/Percussion com Side ×0,5; os novos testes não foram adotados como se tivessem aprovação humana. Woodwinds, Brass, Backing e Synth permanecem com largura original no preview.','',
        '## 4. Masking, clareza e turn-taking','',
        'A análise usa STFT Hann 4096 / hop 2048, potência dos dois canais e seis bandas entre 60 Hz e 20 kHz. Analisa separadamente os trechos 200–207,02; 207,05–218,50; 218,71–224,43; 224,50–230 s. A auditoria temporal usa RMS a cada 100 ms, coatividade e correlação dos envelopes. Sobreposição espectral e atividade indicam competição potencial, não um limiar psicoacústico comprovado.',
        '', '| Seção | Objeto em destaque | Ajustes de suporte |','|---|---|---|']
    for section in r['masking']['sections']:
        trims=', '.join(f'{role}: {gain:g} dB' for role,gain in section['support_trims_db'].items()) or 'Nenhum indicado pelo critério'
        lines.append(f"| {section['start_seconds']:.2f}–{section['end_seconds']:.2f} s | {section['featured'] or 'Posições estáveis'} | {trims} |")
    lines += ['', 'O critério combina sobreposição de bandas >0,75 e RMS relativo >−8 dB. Reduções de suporte são pequenas e usam rampas de 250 ms; Lead, Drums e Bass não recebem esses cortes. Não há EQ global ou corretivo. O detalhe das bandas/potenciais competidores está no relatório de masking.',
        '', f"O relatório também inclui análise somente de leitura das {len(r['masking']['full_song_read_only_section_analysis'])} seções do mapa T001, com pares de possível competição espectral/temporal. O mapa estrutural é provisório, não foi validado musicalmente fora do preview, e nenhum ajuste ou render completo foi produzido para essas seções.",
        '', 'Woodwinds se move durante suas duas frases. Percussion executa uma volta de 360° entre elas (207,05–218,50 s), com breves retenções nos setores. Backing e Synth mantêm suas regiões. Brass alterna lados no intervalo silencioso entre as duas entradas e permanece localizado durante as frases. A auditoria registra o número máximo de objetos expressivos angulares ativos: **'+str(r['maximum_active_angular_movers'])+'**.',
        '', 'Eventos selecionados: Woodwinds aproxima a 0,35 m em 203,15 s; Percussion aproxima a 0,25 m em 210,50 s. A cena musical usa a política parcial, preservando até 2,5 dB adicionais de crescimento calibrado relativamente à casa de cada fonte, sem normalizar cada evento posteriormente. Fora desses eventos, o crescimento adicional é zero.',
        '', 'A comparação na pasta final_comparison é a entrega para escuta. Os primeiros exports internos T004 foram preservados como intermediários anteriores à revisão da referência de ganho; não são recomendações de escuta. A revisão usa ganho vinculado após o plugin e mantém poses/distâncias, sem EQ ou limiter. A aproximação numérica devido ao PCM24 anterior é inferior a um LSB e está documentada.',
        '', '## 5. Preview e comparação T003/T004','']
    for label,e in r['comparison']['matched'].items():lines.append('- '+link(label+' — 200–230 s',e['path']))
    lines += ['', '| Versão | LUFS | True peak |','|---|---:|---:|']
    for label,e in r['comparison']['matched'].items():lines.append(f"| {label} | {e['loudness']['integrated_lufs']:.1f} | {e['loudness']['true_peak_dbtp']:.1f} dBTP |")
    lines += ['', 'Matching usa somente ganho vinculado constante por versão. O crescimento local de aproximação dentro da T004 é preservado. Todos os previews têm 30 s, PCM24, 48 kHz, estereo e 1.440.000 frames, com pre-roll comum de 1 s. Nenhum trimming por atividade.',
        '', '## Spatial homes','', '| Role | Azimute | Elevação | Distância |','|---|---:|---:|---:|']
    for s in scene['sources']:
        h=s['home'];lines.append(f"| {s['source_id']} | {h['azimuth_deg']:g}° | {h['elevation_deg']:g}° | {h['distance_m']:g} m |")
    lines += ['', 'As âncoras centrais permanecem fixas; Guitar e Keyboard ocupam lados frontais opostos com alturas diferentes. As casas dos objetos móveis são referências, com exceções por frase documentadas. Other mantém ganho conservador e identidade pendente.',
        '', '## Relatórios e regressões','',
        f"Verificados {tests['verified_wavs']} WAVs e todos os {tests['protected_music02_files']} arquivos MUSIC 02 anteriores e {tests['protected_tukana_files']} arquivos Tukãna por SHA-256, tamanho e mtime. Baseline T017 e DSP aprovado preservados. Testes de ganho/distância, frames, sequência de objetos, turn-taking, continuidade de blocos e comparação passaram.",'']
    for label,file in [('Relatório técnico','reports/M02_T004_validation.json'),('Compactness','reports/compactness.json'),('Masking/clareza','reports/masking_clarity.json'),('Near-field e calibração','reports/near_field.json'),('Monitor de objetos','reports/object_monitor.json'),('Auditoria angular','reports/angular_separation.json'),('Cena','spatial_scenes/M02_T004_scene.json'),('Ganho dos eventos relativo às casas','reports/event_gain_reference.json'),('Regressões','reports/M02_T004_encoded_regression.json'),('Avaliação humana T003','reports/M02_T003_human_review.json'),('Pedido original e avaliação recebida','reports/M02_T004_user_request.md')]:lines.append('- '+link(label,OUT/file))
    lines += ['', '## Avaliação humana acessível','',
        'Sem exigir nomes: o som veio da frente? Veio de trás? Pareceu acima? Passou perto do ouvido? Você percebeu duas fontes em lugares diferentes? Algum som pareceu circular? A cena ficou mais clara? Algum som ficou artificial? Qual política de aproximação funcionou melhor e com conforto?',
        '', 'Critérios perceptivos permanecem pendentes: localização de objetos, proximidade física extrema, timbre, externalização, naturalidade e conforto. Coordenadas e ausência de clipping não provam sucesso auditivo.',
        '', '**T001, T002, T003 e Tukãna preservadas. Nenhuma promoção, masterização ou música completa renderizada. Aguardar avaliação humana antes de prosseguir.**','']
    path=OUT/'README.md';assert not path.exists();path.write_text('\n'.join(lines),encoding='utf-8');print(path)

if __name__=='__main__':run()
