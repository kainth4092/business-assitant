"use client";

import React from "react";
import {
  BarChart2,
  CheckCircle2,
  BookOpen,
  LifeBuoy,
  X,
  Plus,
  Database,
  Layers,
  ChevronRight,
  History
} from "lucide-react";
import ThemeToggle from "./ThemeToggle";

export default function Sidebar({
  activeTab = "chat",
  onSelectTab = () => {},
  onNewSession = () => {},
  history = [],
  activeQuestionId = null,
  onSelectHistory = () => {},
  systemHealth = null,
  pendingTicketsCount = 0,
  isMobileOpen = false,
  onCloseMobile = () => {}
}) {
  const tabs = [
    {
      id: "chat",
      label: "Analysis",
      fullName: "Live Analysis",
      icon: BarChart2,
      count: history.length > 0 ? history.length : null,
    },
    {
      id: "data-quality",
      label: "Quality",
      fullName: "Data Quality",
      icon: CheckCircle2,
      count: "ETL",
    },
    {
      id: "documents",
      label: "Docs",
      fullName: "Documentation",
      icon: BookOpen,
      count: systemHealth?.indexed_chunks ? `${systemHealth.indexed_chunks}` : null,
    },
    {
      id: "support-desk",
      label: "Support",
      fullName: "Support Desk",
      icon: LifeBuoy,
      count: pendingTicketsCount > 0 ? pendingTicketsCount : null,
      highlight: pendingTicketsCount > 0,
    },
  ];

  return (
    <>
      {/* -------------------------------------------------------------------- */}
      {/* 1. DESKTOP 72px UTILITY RAIL                                         */}
      {/* -------------------------------------------------------------------- */}
      <aside className="fixed left-0 top-0 h-full w-[72px] bg-surface-highest border-r border-border z-40 hidden lg:flex flex-col justify-between items-center py-3.5 select-none transition-colors">
        {/* Top: Logo & Nav items */}
        <div className="flex flex-col items-center w-full gap-4">
          {/* Logo Mark: Two overlapping squares with chartreuse / lime accent */}
          <div className="h-10 w-full flex items-center justify-center">
            <button
              onClick={() => {
                onSelectTab("chat");
                onNewSession();
              }}
              className="w-10 h-10 rounded-md bg-surface border border-border flex items-center justify-center shadow-xs hover:border-accent-lime transition-all group"
              title="Business Assistant · New Analysis"
            >
              <div className="relative w-5 h-5 flex items-center justify-center">
                <span className="absolute w-3.5 h-3.5 rounded-xs bg-accent-lime/20 border border-accent-lime group-hover:scale-105 transition-transform" />
                <span className="absolute w-3.5 h-3.5 rounded-xs bg-surface border border-primary translate-x-1 translate-y-1" />
              </div>
            </button>
          </div>

          {/* Navigation Items */}
          <nav className="flex flex-col items-center w-full gap-2">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  id={`sidebar-tab-${tab.id}`}
                  data-testid={`sidebar-tab-${tab.id}`}
                  onClick={() => onSelectTab(tab.id)}
                  className={`relative flex flex-col items-center justify-center w-12 h-12 rounded-md transition-all group ${
                    isActive
                      ? "bg-surface text-primary border border-border shadow-xs"
                      : "text-muted hover:text-primary hover:bg-surface-high border border-transparent"
                  }`}
                  title={`${tab.fullName} (${tab.label})`}
                  aria-label={tab.fullName}
                >
                  <Icon
                    className={`w-5 h-5 transition-transform group-hover:scale-110 ${
                      isActive ? "text-primary stroke-[2.2]" : "text-muted stroke-[1.8]"
                    }`}
                  />
                  <span
                    className={`font-mono text-[9px] uppercase tracking-wider font-semibold mt-0.5 ${
                      isActive ? "text-primary" : "text-muted"
                    }`}
                  >
                    {tab.label}
                  </span>

                  {/* Badge Counter */}
                  {tab.count !== null && (
                    <span
                      className={`absolute -top-1 -right-1 font-mono text-[9px] px-1 py-0.2 rounded-full font-bold tabular-nums shadow-xs ${
                        tab.highlight
                          ? "bg-accent-crimson text-white animate-pulse"
                          : isActive
                          ? "bg-accent-lime text-accent-lime-contrast"
                          : "bg-surface border border-border text-muted"
                      }`}
                    >
                      {tab.count}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Bottom: Theme Toggle & Telemetry Heartbeat */}
        <div className="flex flex-col items-center w-full gap-2.5 pb-2">
          {/* Theme Toggle */}
          <ThemeToggle />

          {/* Live Telemetry Pill */}
          <div
            className="w-full px-1 pt-2 border-t border-border flex flex-col items-center justify-center text-center"
            title="Postgres 16 · pgvector HNSW Engine Connected"
          >
            <div className="flex items-center gap-1.5 py-0.5 px-1">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-emerald opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-emerald" />
              </span>
              <span className="font-mono text-[8px] text-muted uppercase font-bold tracking-tight">
                LIVE
              </span>
            </div>
            <span className="font-mono text-[8px] text-muted leading-none">
              18ms
            </span>
          </div>
        </div>
      </aside>

      {/* -------------------------------------------------------------------- */}
      {/* 2. MOBILE DRAWER OVERLAY (<1024px)                                   */}
      {/* -------------------------------------------------------------------- */}
      {isMobileOpen && (
        <div
          onClick={onCloseMobile}
          className="fixed inset-0 bg-black/50 backdrop-blur-xs z-50 lg:hidden transition-opacity"
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-72 bg-surface border-r border-border flex flex-col transition-transform duration-normal ease-in-out lg:hidden ${
          isMobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Drawer Header */}
        <div className="p-4 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-surface-container border border-border flex items-center justify-center">
              <span className="w-4 h-4 rounded-xs bg-accent-lime/30 border border-accent-lime" />
            </div>
            <div>
              <h2 className="font-headline text-headline-md text-primary font-bold leading-none">
                Business Assistant
              </h2>
              <span className="font-mono text-[10px] uppercase text-muted tracking-wider">
                Telemetry Console
              </span>
            </div>
          </div>
          <button
            onClick={onCloseMobile}
            className="p-1.5 rounded text-muted hover:text-primary hover:bg-surface-high"
            aria-label="Close sidebar"
          >
            <X className="w-4 h-4 stroke-[2]" />
          </button>
        </div>

        {/* Action: New Session */}
        <div className="p-3 border-b border-border">
          <button
            onClick={() => {
              onNewSession();
              onCloseMobile();
            }}
            className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 text-xs font-semibold rounded bg-accent-lime hover:bg-accent-lime-hover text-accent-lime-contrast font-headline shadow-xs transition-all"
          >
            <Plus className="w-4 h-4 stroke-[2.2]" />
            <span>New Analysis</span>
          </button>
        </div>

        {/* Navigation Tabs */}
        <nav className="p-2 space-y-1 border-b border-border">
          <div className="px-3 py-1.5 font-mono text-[10px] uppercase text-muted font-bold tracking-wider">
            Navigation Views
          </div>
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => {
                  onSelectTab(tab.id);
                  onCloseMobile();
                }}
                className={`w-full flex items-center justify-between px-3 py-2 rounded text-xs font-medium transition-all ${
                  isActive
                    ? "bg-surface-container text-primary font-bold border-l-2 border-accent-lime pl-[10px]"
                    : "text-muted hover:text-primary hover:bg-surface-high"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon className={`w-4 h-4 ${isActive ? "text-primary stroke-[2.2]" : "text-muted stroke-[1.8]"}`} />
                  <span>{tab.fullName}</span>
                </div>
                {tab.count !== null && (
                  <span
                    className={`font-mono text-[10px] px-1.5 py-0.2 rounded border ${
                      tab.highlight
                        ? "bg-accent-crimson text-white font-bold"
                        : isActive
                        ? "bg-accent-lime text-accent-lime-contrast font-bold"
                        : "bg-surface-high text-muted border-border font-medium"
                    }`}
                  >
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Session Log */}
        <div className="flex-1 overflow-y-auto p-2 min-h-0 space-y-1">
          <div className="px-3 py-1.5 font-mono text-[10px] uppercase text-muted font-bold flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <History className="w-3.5 h-3.5 stroke-[2]" />
              <span>Session Log</span>
            </span>
            <span className="tabular-nums font-mono text-[11px] text-muted">
              {history.length}
            </span>
          </div>

          {history.length === 0 ? (
            <div className="p-4 text-xs text-muted text-center font-body">
              No queries logged in this session yet.
            </div>
          ) : (
            history.map((item) => {
              const isSelected = activeQuestionId === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    onSelectTab("chat");
                    onSelectHistory(item.id);
                    onCloseMobile();
                  }}
                  className={`w-full text-left p-2.5 rounded text-xs transition-all border ${
                    isSelected
                      ? "bg-surface-container border-accent-lime/60 text-primary font-semibold"
                      : "border-transparent text-muted hover:text-primary hover:bg-surface-high"
                  }`}
                >
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <span className="text-[10px] font-mono text-accent-cyan font-bold">
                      {item.tag || "QRY"}
                    </span>
                    <span className="text-[10px] font-mono text-muted tabular-nums">
                      {item.timestamp}
                    </span>
                  </div>
                  <p className="text-[12px] line-clamp-2 leading-snug">
                    {item.query}
                  </p>
                </button>
              );
            })
          )}
        </div>

        {/* Drawer Footer */}
        <div className="p-3 border-t border-border flex items-center justify-between">
          <span className="font-mono text-[11px] text-muted font-medium">
            Theme Mode
          </span>
          <ThemeToggle showLabel />
        </div>
      </aside>
    </>
  );
}
