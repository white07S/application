import React from 'react';
import { ControlRelationships } from '../types';

interface Props {
    relationships: ControlRelationships;
}

const Pill: React.FC<{ id: string; label: string }> = ({ id, label }) => (
    <span className="inline-flex items-center gap-1 text-[11px] bg-surface-light border border-border-light rounded px-1.5 py-0.5">
        <span className="font-mono text-text-sub">{id}</span>
        <span className="text-text-sub">·</span>
        <span className="text-text-main">{label}</span>
    </span>
);

const Row: React.FC<{ icon: string; label: string; children: React.ReactNode }> = ({ icon, label, children }) => (
    <div className="flex items-start gap-1.5">
        <span className="material-symbols-outlined text-[14px] text-text-sub mt-0.5 flex-shrink-0">{icon}</span>
        <div className="flex-1 min-w-0">
            <span className="text-[10px] text-text-sub uppercase font-medium tracking-wide block leading-none mb-0.5">
                {label}
            </span>
            <div className="flex flex-wrap gap-1">{children}</div>
        </div>
    </div>
);

export const ControlCardRelationships: React.FC<Props> = ({ relationships }) => {
    const r = relationships;

    return (
        <div className="flex flex-col gap-2 p-3 min-w-0">
            {r.owning_function && (
                <Row icon="account_tree" label="Owning Function">
                    <Pill id={r.owning_function.id} label={r.owning_function.label} />
                </Row>
            )}

            {r.owning_location && (
                <Row icon="location_on" label="Owning Location">
                    <Pill id={r.owning_location.id} label={r.owning_location.label} />
                </Row>
            )}

            {r.related_functions.length > 0 && (
                <Row icon="domain" label="Related Functions">
                    {r.related_functions.map((f) => (
                        <Pill key={f.id} id={f.id} label={f.label} />
                    ))}
                </Row>
            )}

            {r.related_locations.length > 0 && (
                <Row icon="public" label="Related Locations">
                    {r.related_locations.map((l) => (
                        <Pill key={l.id} id={l.id} label={l.label} />
                    ))}
                </Row>
            )}

        </div>
    );
};
