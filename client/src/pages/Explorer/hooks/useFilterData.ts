import { useState, useEffect } from 'react';
import { useAuth } from '../../../auth/useAuth';
import { FlatItem, RiskTaxonomy } from '../types';
import { fetchAUs, fetchRiskThemes } from '../api/explorerApi';

export function useFilterData(asOfDate: string) {
    const { getApiAccessToken } = useAuth();

    const [auItems, setAuItems] = useState<FlatItem[]>([]);
    const [auLoading, setAuLoading] = useState(true);

    const [taxonomies, setTaxonomies] = useState<RiskTaxonomy[]>([]);
    const [riskLoading, setRiskLoading] = useState(true);
    const [auDateWarning, setAuDateWarning] = useState<string | null>(null);
    const [riskDateWarning, setRiskDateWarning] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            setAuLoading(true);
            setRiskLoading(true);
            try {
                const token = await getApiAccessToken();
                if (!token || cancelled) return;

                const [auData, riskData] = await Promise.all([
                    fetchAUs(token, asOfDate),
                    fetchRiskThemes(token, asOfDate),
                ]);

                if (!cancelled) {
                    setAuItems(auData.items.map((i) => ({
                        id: i.id,
                        label: i.label,
                        description: i.description,
                    })));
                    setAuDateWarning(auData.date_warning || null);
                    setTaxonomies(riskData.taxonomies.map((t) => ({
                        id: t.id,
                        name: t.name,
                        themes: t.themes.map((th) => ({ id: th.id, name: th.name })),
                    })));
                    setRiskDateWarning(riskData.date_warning || null);
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
    }, [asOfDate]);

    return {
        aus: { items: auItems, loading: auLoading, dateWarning: auDateWarning },
        riskThemes: { taxonomies, loading: riskLoading, dateWarning: riskDateWarning },
    };
}
