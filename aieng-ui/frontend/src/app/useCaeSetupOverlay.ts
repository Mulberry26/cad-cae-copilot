import { useEffect, useState } from "react";

import { api } from "../api";
import type { CaeSetupOverlayResponse } from "../types";

type UseCaeSetupOverlayArgs = {
  selectedId: string | null;
  /** Re-fetch when the project's geometry/setup is rebuilt. */
  geometryVersion?: string | null;
};

/**
 * Loads the project's CAE setup overlay data (loads, constraints, bound faces,
 * warnings) for the viewer. Absent packages / setups resolve to null so the
 * overlay toggle stays hidden.
 */
export function useCaeSetupOverlay({ selectedId, geometryVersion = null }: UseCaeSetupOverlayArgs) {
  const [overlay, setOverlay] = useState<CaeSetupOverlayResponse | null>(null);

  useEffect(() => {
    setOverlay(null);
  }, [selectedId]);

  useEffect(() => {
    const controller = new AbortController();
    if (!selectedId) return;
    void (async () => {
      try {
        const data = await api.getCaeSetupOverlay(selectedId, controller.signal);
        if (controller.signal.aborted) return;
        setOverlay(data && data.available ? data : null);
      } catch {
        if (!controller.signal.aborted) setOverlay(null);
      }
    })();
    return () => {
      controller.abort();
    };
  }, [selectedId, geometryVersion]);

  return { caeSetupOverlay: overlay };
}
