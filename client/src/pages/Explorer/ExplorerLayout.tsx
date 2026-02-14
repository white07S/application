import React from 'react';
import { useFilterState } from './hooks/useFilterState';
import { FilterSidebar } from './components/FilterSidebar';

const ExplorerLayout: React.FC = () => {
    const [state, dispatch] = useFilterState();

    return (
        <main>
            <div className="w-full max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px] mx-auto px-3 sm:px-4">
                <div className="flex">
                    {/* Sticky filter sidebar — fixed height, no page scroll */}
                    <div className="sticky top-12 h-[calc(100vh-48px)] py-4">
                        <FilterSidebar state={state} dispatch={dispatch} />
                    </div>

                    {/* Content area */}
                    <div className="flex-1 min-w-0 py-4 pl-4 flex flex-col gap-4">
                        <div className="text-text-sub text-sm">
                            <p>Select filters and click Apply to view data.</p>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    );
};

export default ExplorerLayout;
