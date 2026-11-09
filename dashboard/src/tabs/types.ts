import type { Row, Tool } from "../lib/analytics";
import type { DatasetId } from "../lib/data";

export interface TabProps {
  /** Execuções do recorte atual (filtros aplicados). */
  view: Row[];
  /** Ferramentas selecionadas, na ordem fixa do estudo. */
  tools: Tool[];
  log: boolean;
  dark: boolean;
  dataset: DatasetId;
}
