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

const Field: React.FC<{ label: string; value: React.ReactNode; mono?: boolean }> = ({ label, value, mono }) => {
    if (value === null || value === undefined || value === '') return null;
    return (
        <div className="flex gap-2 py-0.5">
            <span className="text-[10px] text-text-sub w-36 shrink-0 pt-px">{label}</span>
            <span className={`text-[11px] text-text-main break-words min-w-0 ${mono ? 'font-mono' : ''}`}>{value}</span>
        </div>
    );
};

const BoolField: React.FC<{ label: string; value: boolean | null }> = ({ label, value }) => {
    if (value === null || value === undefined) return null;
    return (
        <div className="flex gap-2 py-0.5">
            <span className="text-[10px] text-text-sub w-36 shrink-0 pt-px">{label}</span>
            <span className={`text-[11px] font-medium ${value ? 'text-green-700' : 'text-gray-400'}`}>
                {value ? 'Yes' : 'No'}
            </span>
        </div>
    );
};

const TextBlock: React.FC<{ label: string; value: string | null }> = ({ label, value }) => {
    if (!value) return null;
    return (
        <div className="py-1">
            <span className="text-[10px] text-text-sub block mb-0.5">{label}</span>
            <p className="text-[11px] text-text-main leading-relaxed bg-surface-light rounded p-2 whitespace-pre-wrap">{value}</p>
        </div>
    );
};

export const DetailsTab: React.FC<Props> = ({ data }) => {
    const c = data.control;

    return (
        <div>
            {/* Control Info */}
            <Section title="Control Information" icon="info">
                <Field label="Title" value={c.control_title} />
                <TextBlock label="Description" value={c.control_description} />
                <Field label="Status" value={c.control_status} />
                <Field label="Hierarchy Level" value={c.hierarchy_level} />
                <BoolField label="Key Control" value={c.key_control} />
                <Field label="Frequency" value={c.execution_frequency} />
                <Field label="Preventative / Detective" value={c.preventative_detective} />
                <Field label="Manual / Automated" value={c.manual_automated} />
                <BoolField label="Four Eyes Check" value={c.four_eyes_check} />
                <Field label="Created On" value={c.control_created_on ? new Date(c.control_created_on).toLocaleDateString() : null} />
                <Field label="Last Modified" value={c.last_modified_on ? new Date(c.last_modified_on).toLocaleDateString() : null} />
            </Section>

            {/* Evidence */}
            <Section title="Evidence" icon="fact_check">
                <TextBlock label="Evidence Description" value={c.evidence_description} />
                <TextBlock label="Local Functional Information" value={c.local_functional_information} />
            </Section>

            {/* People */}
            <Section title="People" icon="group">
                <Field label="Owner" value={c.control_owner} />
                <Field label="Owner GPN" value={c.control_owner_gpn} mono />
                <Field label="Delegate" value={data.control_delegate} />
                <Field label="Delegate GPN" value={data.control_delegate_gpn} mono />
                <Field label="Assessor" value={data.control_assessor} />
                <Field label="Assessor GPN" value={data.control_assessor_gpn} mono />
                <Field label="Created By" value={data.control_created_by} />
                <Field label="Created By GPN" value={data.control_created_by_gpn} mono />
                <Field label="Last Modified By" value={data.last_control_modification_requested_by} />
                <Field label="Last Modified By GPN" value={data.last_control_modification_requested_by_gpn} mono />
                {data.control_administrator.length > 0 && (
                    <Field label="Administrators" value={data.control_administrator.join(', ')} />
                )}
            </Section>

            {/* Compliance */}
            <Section title="Compliance" icon="policy">
                <BoolField label="SOX Relevant" value={c.sox_relevant} />
                <BoolField label="CCAR Relevant" value={data.ccar_relevant} />
                <BoolField label="BCBS239 Relevant" value={data.bcbs239_relevant} />
                <TextBlock label="SOX Rationale" value={data.sox_rationale} />
                {data.sox_assertions.length > 0 && (
                    <Field label="SOX Assertions" value={data.sox_assertions.join(', ')} />
                )}
            </Section>
        </div>
    );
};
