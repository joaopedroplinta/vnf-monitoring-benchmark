import { useState } from "react";
import { METRICS } from "../lib/analytics";
import { barTraces } from "../lib/charts";
import { Chart } from "../components/Chart";
import { Card, Info, SectionTitle, Select } from "../components/ui";
import type { TabProps } from "./types";

type ResourceMetric = keyof typeof METRICS;

export function Resources({ view, tools, dark }: TabProps) {
  const [metric, setMetric] = useState<ResourceMetric>("mem_obs_mb");

  return (
    <div className="flex flex-col gap-4">
      <SectionTitle title="O custo em CPU, memória e validação do WAF" sub="Selecione qual componente e métrica você quer comparar entre as ferramentas." />
      <Select
        label="Métrica de recursos ou validação"
        value={metric}
        onChange={setMetric}
        options={(Object.keys(METRICS) as ResourceMetric[]).map((m) => ({ value: m, label: METRICS[m] }))}
      />
      {(metric === "mem_waf_mb" || metric === "cpu_waf") && tools.includes("Docker") && (
        <Info>No Docker, os recursos do WAF são medidos pelo cgroup do contêiner (incluindo páginas de cache do kernel). Nas demais ferramentas, pelo processo via psutil (RSS). As medições não são diretamente comparáveis em escala absoluta.</Info>
      )}
      {metric === "cpu_obs" && (
        <Info>A CPU do observador é ruidosa neste experimento. Os intervalos de confiança podem ser da ordem da própria média; esta métrica não permite declarar uma ferramenta vencedora em CPU.</Info>
      )}
      {metric === "inspect_avg_ms" && (
        <Info>Métrica de validação funcional (Seção 4.5): o tempo médio de inspeção por mensagem no WAF permanece estável (~0,080 ms na coleta oficial) em todas as ferramentas, comprovando que nenhum observador degradou a execução interna da VNF.</Info>
      )}
      {metric === "inspect_pct" && (
        <Info>Fração de N efetivamente inspecionada pelo WAF: na Coleta Oficial (1 processo), varia de ~99,8% (100 mil) a ~62,4% (2 M). Na bateria de Inspeção Integral (4 processos), atinge 100% em todos os volumes.</Info>
      )}
      <Card>
        <SectionTitle title={METRICS[metric]} sub="Média por volume nominal · barras de erro: IC95%" />
        <Chart
          label={`Gráfico de barras: ${METRICS[metric]} por volume e ferramenta`}
          dark={dark}
          height={400}
          data={barTraces(view, tools)(metric)}
          layout={{ barmode: "group", yaxis: { title: { text: METRICS[metric], font: { size: 11 } } } }}
        />
      </Card>
      <p className="text-xs text-muted">CPU pode ultrapassar 100% quando o processo (ou conjunto de processos do WAF) utiliza mais de um núcleo lógico.</p>
    </div>
  );
}
