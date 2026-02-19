import { useState, useEffect } from 'react';
import { useAuth } from '../../../auth/useAuth';
import { FlatItem, RiskTaxonomy } from '../types';
import { fetchAUs, fetchRiskThemes } from '../api/explorerApi';

export function useFilterData() {
    const { getApiAccessToken } = useAuth();

    const [auItems, setAuItems] = useState<FlatItem[]>([]);
    const [auLoading, setAuLoading] = useState(true);

    const [taxonomies, setTaxonomies] = useState<RiskTaxonomy[]>([]);
    const [riskLoading, setRiskLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            setAuLoading(true);
            setRiskLoading(true);
            try {
                const token = await getApiAccessToken();
                if (!token || cancelled) return;

                const [auData, riskData] = await Promise.all([
                    fetchAUs(token),
                    fetchRiskThemes(token),
                ]);

                if (!cancelled) {
                    setAuItems(auData.items.map((i) => ({
                        id: i.id,
                        label: i.label,
                        description: i.description,
                        function_node_id: i.function_node_id ?? undefined,
                        location_node_id: i.location_node_id ?? undefined,
                        location_type: i.location_type ?? undefined,
                    })));
                    setTaxonomies(riskData.taxonomies.map((t) => ({
                        id: t.id,
                        name: t.name,
                        themes: t.themes.map((th) => ({ id: th.id, name: th.name })),
                    })));
                }
            } catch (err: any) {
                // Errors are non-fatal for individual sections
            } finally {
                if (!cancelled) {
                    setAuLoading(false);
                    setRiskLoading(false);
                }
            }
        };
        load();
        return () => { cancelled = true; };
    }, [getApiAccessToken]);

    return {
        aus: { items: auItems, loading: auLoading },
        riskThemes: { taxonomies, loading: riskLoading },
    };
}
