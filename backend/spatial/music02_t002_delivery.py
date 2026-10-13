"""Create an audition index and technical delivery without touching references."""
from pathlib import Path
from music02_t002 import OUT,load

def link(entry,title):
    path=Path(entry['level_matched']['path']).relative_to(OUT).as_posix()
    return f'- [{title}]({path})'

def main():
    r=load(OUT/'reports/M02_T002_validation.json');lead=load(OUT/'reports/lead_diagnosis.json')
    test=load(OUT/'reports/M02_T002_encoded_regression.json')
    assert r['objective_status']=='PASS' and test['status']=='PASS'
    lines=['# MUSIC 02 — M02-T002','',
        'Variante experimental concluída; validação técnica **PASS**. Superioridade perceptiva **PENDENTE**. Referência M02-T001 e todo o projeto Tukãna preservados por hash, tamanho e data de modificação.','',
        '## Comparação principal — 200–230 s','',
        link(r['comparison']['T001_baseline'],'M02-T001 referência level-matched'),
        link(r['comparison']['T002_proximity_compact_lead'],'M02-T002 proximidade + Lead compacto, candidato'),
        link(r['comparison']['T002_proximity_original_lead_control'],'M02-T002 proximidade com Lead estéreo original, controle'),'',
        'Todos medem −20,7 LUFS, 30 s / 1.440.000 frames, estéreo PCM24 a 48 kHz. True peaks: aproximadamente −6,0/−6,1 dBTP. Não houve limiter, mastering ou render completo. A cópia de comparação da T001 recebeu apenas ganho comum transparente; o arquivo original da T001 continua intacto.','',
        '## Diagnóstico da voz','',
        f"O Lead completo tem diferença RMS L−R de **{lead['original_full_file']['energy_difference_left_minus_right_db']:+.3f} dB** e correlação **{lead['original_full_file']['correlation']:.3f}**. Isso não caracteriza um stem globalmente à esquerda.", '',
        f"No intervalo 200–230 s, o direito está **0,906 dB** acima do esquerdo; correlação original **{lead['original_preview']['correlation']:.3f}**, processada T001 **{lead['T001_processed_preview']['correlation']:.3f}**. A diferença RMS processada L−R é cerca de −0,007 dB: níveis praticamente iguais. A imagem de fase/largura, e não excesso de energia esquerda, é uma hipótese relevante.", '',
        'Nesse intervalo o Lead está aproximadamente **17,6 dB abaixo de Backing Vocals** em RMS. Backing estava à esquerda e elevado; pode haver mascaramento ou identificação dessa camada como voz principal. Essa hipótese precisa de escuta dos monitores, não de correção arbitrária do azimute. A média mono L+R do trecho reduziria RMS em aproximadamente 4,39 dB, evidenciando cancelamento parcial.','',
        f"A/B/C usam o mesmo trecho **{lead['diagnostic_interval']['start_seconds']:.1f}–{lead['diagnostic_interval']['start_seconds']+12:.1f} s**, posição frontal 0°/0° e distância 3 m. Monitores receberam um ganho comum seguro para audição confortável, seguido de matching por ganho vinculado.", '',
        link(r['listening_monitors']['lead_diagnostics']['A_stereo'],'Lead A — estéreo original, frente'),
        link(r['listening_monitors']['lead_diagnostics']['B_compact_side50'],'Lead B — lado M/S reduzido a 50%, frente'),
        link(r['listening_monitors']['lead_diagnostics']['C_dual_mono_diagnostic'],'Lead C — mono diagnóstico sem soma entre canais'),'',
        'B atenua somente o componente Side antes do dearVR e restaura RMS com um único ganho para ambos os canais. Não mexe no parâmetro Stereo Width do plugin. Correlação pós-dearVR no diagnóstico: A −0,471; B +0,178; C +0,997. Isso descreve coerência, não prova externalização frontal nem preferência.','',
        'C duplica o canal de maior RMS, com ganho vinculado, evitando cancelar canais opostos. Descarta conteúdo exclusivo do outro canal e não foi adotado no mix. B é candidato de audição, com o controle de Lead original disponível. Não aplicar nenhuma dessas decisões à música inteira automaticamente.','',
        'RMS L/R, peaks L/R, diferença de energia, correlação, proporção de energia Side e relação Side/Mid originais e processados estão em [lead_diagnosis.json](reports/lead_diagnosis.json) e [adendo](reports/lead_diagnosis_addendum.json).','',
        '## Distâncias próximas','',
        'Controle raw calibrado novamente pelos parâmetros do plugin instalado, sem importar módulos T018. O mapeamento derivado dos endpoints 0,1–30 m concorda com a calibração aprovada de 3 m. Foram renderizados **0,35; 0,50; 0,75; 1,00; 1,50; 2,00; 3,00 m**, para Woodwinds e Backing, com mesma entrada e pose em cada varredura. Nenhum áudio a 0,1 m foi renderizado.','',
        'O display do plugin arredonda a 0,1 m. 0,35 e 0,75 m são alvos nominais raw contínuos, sem medição física independente em centímetros. Pose preservou o controle de distância. Todos os arquivos permaneceram finitos, sem clipping ou true peak inseguro. Localização física e estabilidade perceptiva ficam pendentes.','',
        '| Distância | Atenuação vinculada para igualar RMS a 3 m |','|---:|---:|']
    for item in r['distance_analysis']['woodwinds']['static_calibration']['records']:
        lines.append(f"| {item['distance_m']:.2f} m | {item['linked_compensation_db']:+.2f} dB |")
    lines += ['',
        'As duas fontes tiveram curvas praticamente iguais: o aumento de nível sem compensação chega a cerca de 6,83 dB em 0,35 m. A variante aplica correção de ganho vinculada interpolada pelas medições, com transição suave; não acrescenta filtros espectrais. Os monitores estáticos e dinâmicos também são igualados em LUFS.','',
        'No controle DirectSignal, as diferenças espectrais em 0,75 versus 3 m foram pequenas nas bandas centrais: aproximadamente 0,000–0,010 dB entre 60 Hz e 6 kHz. Nas bandas extremas medidas, até cerca de 0,55 dB. Essas variações não demonstram, sozinhas, sensação física de proximidade. O efeito compensado pode ser sutil; a avaliação humana é decisiva.','',
        'As varreduras de oito segundos, com os mesmos trechos por fonte, estão abaixo. Cada arquivo está level-matched dentro de sua própria comparação:','']
    for role,title in [('woodwinds','Woodwinds'),('backing_vocals','Backing Vocals')]:
        lines += [f'### {title} — distância','']
        for label,entry in r['listening_monitors']['distance_'+role].items():
            lines.append(link(entry,label))
        lines.append('')
    lines += ['## Aproximação expressiva e órbita','',
        'Woodwinds preserva exatamente a trajetória angular M02-T001. Na frase selecionada de **200,0–207,019 s**, a distância nominal percorre **2,5 → 1,5 → 0,75 → 1,2 → 2,0 m**, com aproximação/retorno a 3 m fora do evento. Não foi automatizada a música inteira.','',
        'Backing passa para **−45° / elevação 4°**, com 1,5 m no preview e um evento de resposta perto de **215,5 s**, chegando nominalmente a 0,75 m e retornando a 1,5 m. A escolha usa atividade de Backing elevada e baixa energia de Lead. A camada segue com ganho relativo conservador e controle adicional de loudness.','',
        'Além da curva RMS por distância, o mix usa ajuste vinculado global por stem para igualar a loudness integrada à referência: '+', '.join(f"{role} {value:+.1f} dB" for role,value in r['main_stem_level_control_db'].items())+'. Isso reduz a confusão de nível médio; não promete loudness instantânea idêntica em cada momento.','',
        link(r['listening_monitors']['woodwinds_proximity']['baseline'],'Woodwinds — trajetória original, distância 3 m'),
        link(r['listening_monitors']['woodwinds_proximity']['proximity_candidate'],'Woodwinds — aproximação compensada'),
        link(r['listening_monitors']['backing_vocals_proximity']['baseline'],'Backing — referência M02-T001'),
        link(r['listening_monitors']['backing_vocals_proximity']['proximity_candidate'],'Backing — mais próximo, menos lateral/elevado'),'',
        'Percussion preserva **80° → 440°**, elevação, distância 3 m e instantes originais. A versão compacta só reduz Side antes do plugin, com restauração RMS vinculada. Não altera a órbita nem foi escolhida para o mix. Isso isola largura da fonte; HRTF, elevação e distância não foram variados nesse par, então a causa de uma eventual ambiguidade frente/trás continua inconclusiva.','',
        link(r['listening_monitors']['percussion_orbit']['original_orbit'],'Percussion — órbita original isolada'),
        link(r['listening_monitors']['percussion_orbit']['compact_orbit'],'Percussion — mesma órbita, fonte compacta'),'',
        'Brass conserva a lógica episódica e Other conserva seu tratamento enquanto aguarda identificação auditiva. Os demais stems foram reutilizados diretamente dos exports T001, sem reprocessamento espacial.','',
        '## Validação e preservação','',
        f"- {test['verified_pcm24_wavs']} WAVs de diagnóstico/controle/export foram verificados por hash, PCM24, 48 kHz, estéreo e duração de 8, 12 ou 30 s. Para escuta, usar os links acima; os demais são evidência de medição.",
        '- Comparação principal: diferença de loudness reportada 0,0 LU; true peaks −6,0 a −6,1 dBTP.',
        '- Ausência de NaN/Inf, clipping e outliers de continuidade de bloco pelo critério aprovado. Pre-roll de 1 s comum, mesma origem absoluta e mesma janela, sem trimming por atividade.',
        '- Keyframes angulares Woodwinds/Percussion idênticos aos originais; wrapping ±180° contínuo e órbita 360° preservada.',
        f"- Regressão a 3 m, ganho constante e trajetória de 360°: maior erro renderer experimental versus adapter T017 **{test['fixed_3m_constant_gain_renderer_max_error']:.3g}**. A variante suaviza seu ganho vinculado entre blocos; o adapter aprovado permanece intocado.",
        '- Importer legado, distância fixa, interpolações e arquivos DSP/composer/mastering da tag T017 passaram nas regressões. Nenhum import T018 e nenhuma mudança no plugin Clarity, Stereo Width, occlusion, reflections ou HRTF.',
        '- Todos os arquivos anteriores MUSIC 02 e todos os arquivos Tukãna: conteúdo, tamanho e mtime preservados. Hash da B2 T017 e da referência M02-T001 confirmados.', '',
        'Nenhum teste objetivo demonstra que o Lead já está à frente, que as fontes ficaram fisicamente mais próximas ou que a variante é superior. Esses critérios permanecem dependentes da avaliação humana.', '',
        '## Evidências','',
        '- [Cena M02-T002](spatial_scenes/M02_T002_proximity_centering_scene.json)',
        '- [Relatório técnico completo e métricas](reports/M02_T002_validation.json)',
        '- [Regressões e arquivos codificados](reports/M02_T002_encoded_regression.json)',
        '- [Calibração do controle de distância](reports/distance_parameter_audit.json)',
        '- [Métricas Woodwinds por distância](reports/distance_woodwinds.json)',
        '- [Métricas Backing por distância](reports/distance_backing_vocals.json)',
        '- [Diagnóstico da órbita](reports/percussion_orbit_diagnosis.json)',
        '- [Avaliação humana T001 registrada separadamente](reports/M02_T001_human_review.json)', '',
        'Os experimentos ficam exclusivamente em `experiments/M02_T002`; a baseline aprovada não adota distância dinâmica. Os scripts recusam iniciar sobre diretórios/evidências já existentes. Não alterar ou apagar a referência anterior para repetir o teste; usar um novo namespace.','',
        '**Aguardar avaliação humana**: Lead frontal/central e natural; Woodwinds mais perto com clareza; Backing próximo sem roubar o centro; frente/trás da órbita; proximidade sem aumento aparente de volume; imersão, transientes e conforto. Nenhum render completo ou mastering antes dessa avaliação.','']
    path=OUT/'README.md';assert not path.exists();path.write_text('\n'.join(lines),encoding='utf-8');print(path)

if __name__=='__main__':main()
