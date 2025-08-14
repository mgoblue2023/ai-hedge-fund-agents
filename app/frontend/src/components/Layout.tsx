import { BottomPanel } from '@/components/panels/bottom/bottom-panel';
import { LeftSidebar } from '@/components/panels/left/left-sidebar';
import { RightSidebar } from '@/components/panels/right/right-sidebar';
import { TabBar } from '@/components/tabs/tab-bar';
import { TabContent } from '@/components/tabs/tab-content';
import { SidebarProvider } from '@/components/ui/sidebar';
import { FlowProvider, useFlowContext } from '@/contexts/flow-context';
import { LayoutProvider, useLayoutContext } from '@/contexts/layout-context';
import { TabsProvider, useTabsContext } from '@/contexts/tabs-context';
import { useLayoutKeyboardShortcuts } from '@/hooks/use-keyboard-shortcuts';
import { cn } from '@/lib/utils';
import { SidebarStorageService } from '@/services/sidebar-storage';
import { TabService } from '@/services/tab-service';
import { ReactFlowProvider } from '@xyflow/react';
import { ReactNode, useEffect, useState } from 'react';
import { TopBar } from './layout/top-bar';

function LayoutContent({ children }: { children: ReactNode }) {
  const { reactFlowInstance } = useFlowContext();
  const { openTab, tabs } = useTabsContext(); // ← include tabs
  const { isBottomCollapsed, expandBottomPanel, collapseBottomPanel, toggleBottomPanel } = useLayoutContext();

const [isLeftCollapsed, setIsLeftCollapsed] = useState(() =>
  SidebarStorageService.loadLeftSidebarState(true)
);
const [isRightCollapsed, setIsRightCollapsed] = useState(() =>
  SidebarStorageService.loadRightSidebarState(true)
);


  const [leftSidebarWidth, setLeftSidebarWidth] = useState(280);
  const [rightSidebarWidth, setRightSidebarWidth] = useState(280);
  const [bottomPanelHeight, setBottomPanelHeight] = useState(300);

  const handleSettingsClick = () => {
    const tabData = TabService.createSettingsTab();
    openTab(tabData);
  };

  useLayoutKeyboardShortcuts(
    () => setIsRightCollapsed(!isRightCollapsed),
    () => setIsLeftCollapsed(!isLeftCollapsed),
    () => reactFlowInstance.fitView({ padding: 0.1, duration: 500 }),
    undefined,
    undefined,
    toggleBottomPanel,
    handleSettingsClick,
  );

  useEffect(() => {
    SidebarStorageService.saveLeftSidebarState(isLeftCollapsed);
  }, [isLeftCollapsed]);

  useEffect(() => {
    SidebarStorageService.saveRightSidebarState(isRightCollapsed);
  }, [isRightCollapsed]);

  const getSidebarBasedStyle = () => {
    let left = 0;
    let right = 0;
    if (!isLeftCollapsed) left = leftSidebarWidth;
    if (!isRightCollapsed) right = rightSidebarWidth;
    return { left: `${left}px`, right: `${right}px` };
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden relative bg-background">
      {/* Top bar */}
      <TopBar
        isLeftCollapsed={isLeftCollapsed}
        isRightCollapsed={isRightCollapsed}
        isBottomCollapsed={isBottomCollapsed}
        onToggleLeft={() => setIsLeftCollapsed(!isLeftCollapsed)}
        onToggleRight={() => setIsRightCollapsed(!isRightCollapsed)}
        onToggleBottom={toggleBottomPanel}
        onSettingsClick={handleSettingsClick}
      />

      {/* Tabs */}
      <div className="absolute top-0 z-10 transition-all duration-200" style={getSidebarBasedStyle()}>
        <TabBar />
      </div>

      {/* Main content area */}
      <main
        className="absolute inset-0 overflow-hidden relative"  // ← make relative
        style={{
          left: !isLeftCollapsed ? `${leftSidebarWidth}px` : '0px',
          right: !isRightCollapsed ? `${rightSidebarWidth}px` : '0px',
          top: '40px', // tab bar height
          bottom: !isBottomCollapsed ? `${bottomPanelHeight}px` : '0px',
        }}
      >
        <TabContent className="h-full w-full" />
        {/* Show children when there are NO tabs open */}
        {tabs.length === 0 && (
          <div className="absolute inset-0">
            {children}
          </div>
        )}
      </main>

      {/* Left sidebar */}
      <div
        className={cn(
          "absolute top-0 left-0 z-30 h-full transition-transform",
          isLeftCollapsed && "transform -translate-x-full opacity-0"
        )}
      >
        <LeftSidebar
          isCollapsed={isLeftCollapsed}
          onCollapse={() => setIsLeftCollapsed(true)}
          onExpand={() => setIsLeftCollapsed(false)}
          onWidthChange={setLeftSidebarWidth}
        />
      </div>

      {/* Right sidebar */}
      <div
        className={cn(
          "absolute top-0 right-0 z-30 h-full transition-transform",
          isRightCollapsed && "transform translate-x-full opacity-0"
        )}
      >
        <RightSidebar
          isCollapsed={isRightCollapsed}
          onCollapse={() => setIsRightCollapsed(true)}
          onExpand={() => setIsRightCollapsed(false)}
          onWidthChange={setRightSidebarWidth}
        />
      </div>

      {/* Bottom panel */}
      <div
        className={cn(
          "absolute bottom-0 z-20 transition-transform",
          isBottomCollapsed && "transform translate-y-full opacity-0"
        )}
        style={getSidebarBasedStyle()}
      >
        <BottomPanel
          isCollapsed={isBottomCollapsed}
          onCollapse={collapseBottomPanel}
          onExpand={expandBottomPanel}
          onToggleCollapse={toggleBottomPanel}
          onHeightChange={setBottomPanelHeight}
        />
      </div>
    </div>
  );
}

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <SidebarProvider defaultOpen={true}>
      <ReactFlowProvider>
        <FlowProvider>
          <TabsProvider>
            <LayoutProvider>
              <LayoutContent>{children}</LayoutContent>
            </LayoutProvider>
          </TabsProvider>
        </FlowProvider>
      </ReactFlowProvider>
    </SidebarProvider>
  );
}
