import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

interface ExplorerOption {
    id: string;
    label: string;
    icon: string;
    path: string;
}

const explorerOptions: ExplorerOption[] = [
    { id: 'controls', label: 'Controls', icon: 'shield', path: '/explorer/controls' },
    { id: 'events', label: 'Events', icon: 'event_note', path: '/explorer/events' },
    { id: 'issues', label: 'Issues', icon: 'report_problem', path: '/explorer/issues' },
];

interface ExplorerSelectorProps {
    disabled?: boolean;
}

export const ExplorerSelector: React.FC<ExplorerSelectorProps> = ({ disabled = false }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [isCompactMode, setIsCompactMode] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);
    const navigate = useNavigate();
    const location = useLocation();

    const isActive = location.pathname.startsWith('/explorer');
    const currentOption = explorerOptions.find(opt => location.pathname.startsWith(opt.path));

    // Check screen width for compact mode (icons only on medium screens)
    useEffect(() => {
        const checkWidth = () => {
            setIsCompactMode(window.innerWidth < 1024);
            // Close expanded if screen gets too small
            if (window.innerWidth < 768) {
                setIsExpanded(false);
            }
        };

        checkWidth();
        window.addEventListener('resize', checkWidth);
        return () => window.removeEventListener('resize', checkWidth);
    }, []);

    // Close on click outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setIsExpanded(false);
            }
        };

        if (isExpanded) {
            document.addEventListener('mousedown', handleClickOutside);
        }
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [isExpanded]);

    // Close on escape
    useEffect(() => {
        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') setIsExpanded(false);
        };

        if (isExpanded) {
            document.addEventListener('keydown', handleEscape);
        }
        return () => document.removeEventListener('keydown', handleEscape);
    }, [isExpanded]);

    const handleSelect = (option: ExplorerOption) => {
        setIsExpanded(false);
        navigate(option.path);
    };

    const handleExplorerClick = () => {
        if (disabled) return;
        setIsExpanded(!isExpanded);
    };

    return (
        <div ref={containerRef} className="flex items-center">
            {/* Explorer button - always visible */}
            <button
                onClick={handleExplorerClick}
                className={`
                    flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors group
                    ${isActive ? 'text-primary bg-surface-light' : 'text-text-sub hover:text-text-main hover:bg-surface-light'}
                    ${disabled ? 'opacity-50 pointer-events-none grayscale' : ''}
                `}
            >
                <span className={`material-symbols-outlined text-[16px] ${isActive ? 'text-primary' : 'text-text-sub group-hover:text-primary'}`}>
                    {currentOption ? currentOption.icon : 'explore'}
                </span>
                {currentOption ? currentOption.label : 'Explorer'}
                <span
                    className={`material-symbols-outlined text-[12px] text-text-sub transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
                >
                    chevron_right
                </span>
            </button>

            {/* Expanded options - slides out horizontally */}
            <div
                className={`
                    flex items-center overflow-hidden transition-all duration-200 ease-out
                    ${isExpanded ? 'max-w-[400px] opacity-100 ml-0' : 'max-w-0 opacity-0 ml-0'}
                `}
            >
                {/* Options container - elevated with shadow to distinguish from header */}
                <div className="flex items-center bg-white border border-border-light shadow-md ml-1 px-1 py-0.5">
                    {explorerOptions.map((option, index) => (
                        <React.Fragment key={option.id}>
                            {index > 0 && (
                                <div className="w-px h-4 bg-border-light mx-0.5" />
                            )}
                            <button
                                onClick={() => handleSelect(option)}
                                title={option.label}
                                className={`
                                    flex items-center gap-1 px-2.5 py-1 text-xs font-medium transition-colors group
                                    ${currentOption?.id === option.id
                                        ? 'text-primary bg-primary/10'
                                        : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                                    }
                                `}
                            >
                                <span className={`material-symbols-outlined text-[14px] ${currentOption?.id === option.id ? 'text-primary' : 'group-hover:text-primary'}`}>
                                    {option.icon}
                                </span>
                                {/* Hide labels on medium screens (768-1024px) to save space */}
                                <span className={isCompactMode ? 'hidden' : ''}>
                                    {option.label}
                                </span>
                            </button>
                        </React.Fragment>
                    ))}
                </div>
            </div>
        </div>
    );
};
