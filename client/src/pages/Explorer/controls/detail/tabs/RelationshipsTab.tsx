import React from 'react';
import type { ControlDetailData } from '../../types';

interface Props {
    data: ControlDetailData;
}

const Section: React.FC<{ title: string; icon: string; children: React.ReactNode }> = ({ title, icon, children }) => (
    <div className="mb-4">
        <div className="flex items-center gap-1.5 mb-2 pb-1 border-b border-border-light">
            <span className="material-symbols-outlined text-[14px] text-text-sub">{icon}</span>
            <span className="text-[11px] font-semibold text-text-main uppercase tracking-wide">{title}</span>
        </div>
        {children}
    </div>
);

const ItemRow: React.FC<{ id: string; name?: string | null; badge?: string }> = ({ id, name, badge }) => (
    <div className="flex items-center gap-2 py-1 px-2 rounded hover:bg-surface-light">
        <span className="text-[11px] font-mono text-text-sub shrink-0">{id}</span>
        {name && <span className="text-[11px] text-text-main truncate">{name}</span>}
        {badge && (
            <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 font-medium uppercase shrink-0">
                {badge}
            </span>
        )}
    </div>
);

const EmptyState: React.FC<{ text: string }> = ({ text }) => (
    <div className="py-2 text-[10px] text-text-sub italic">{text}</div>
);

export const RelationshipsTab: React.FC<Props> = ({ data }) => {
    const rels = data.relationships;

    return (
        <div>
            {/* Parent */}
            <Section title="Parent Control" icon="arrow_upward">
                {rels.parent ? (
                    <ItemRow id={rels.parent.id} name={rels.parent.name} badge="Parent" />
                ) : (
                    <EmptyState text="No parent control" />
                )}
            </Section>

            {/* Children */}
            <Section title="Child Controls" icon="arrow_downward">
                {rels.children.length > 0 ? (
                    rels.children.map(c => (
                        <ItemRow key={c.id} id={c.id} name={c.name} />
                    ))
                ) : (
                    <EmptyState text="No child controls" />
                )}
            </Section>

            {/* Owning Function & Location */}
            <Section title="Owning Function" icon="apartment">
                {rels.owns_functions.length > 0 ? (
                    rels.owns_functions.map(f => (
                        <ItemRow key={f.id} id={f.id} name={f.name} />
                    ))
                ) : (
                    <EmptyState text="No owning function" />
                )}
            </Section>

            <Section title="Owning Location" icon="location_on">
                {rels.owns_locations.length > 0 ? (
                    rels.owns_locations.map(l => (
                        <ItemRow key={l.id} id={l.id} name={l.name} />
                    ))
                ) : (
                    <EmptyState text="No owning location" />
                )}
            </Section>

            {/* Related Functions & Locations */}
            <Section title="Related Functions" icon="device_hub">
                {rels.related_functions.length > 0 ? (
                    rels.related_functions.map(f => (
                        <ItemRow key={f.id} id={f.id} name={f.name} />
                    ))
                ) : (
                    <EmptyState text="No related functions" />
                )}
            </Section>

            <Section title="Related Locations" icon="pin_drop">
                {rels.related_locations.length > 0 ? (
                    rels.related_locations.map(l => (
                        <ItemRow key={l.id} id={l.id} name={l.name} />
                    ))
                ) : (
                    <EmptyState text="No related locations" />
                )}
            </Section>

            {/* Risk Themes */}
            <Section title="Risk Themes" icon="category">
                {rels.risk_themes.length > 0 ? (
                    rels.risk_themes.map(t => (
                        <ItemRow key={t.id} id={t.id} name={t.name} />
                    ))
                ) : (
                    <EmptyState text="No risk themes assigned" />
                )}
            </Section>
        </div>
    );
};
