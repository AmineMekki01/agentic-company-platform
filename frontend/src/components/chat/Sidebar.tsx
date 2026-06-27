import { useState, useRef, useEffect } from "react";
import { Bot, ChevronDown, ChevronRight, Folder, FolderPlus, LogOut, MessageSquare, MoreHorizontal, Pencil, Plus, Search, Settings, Trash2, X } from "lucide-react";
import { Link } from "react-router-dom";

import ThemeToggle from "@/components/ThemeToggle";
import type { Conversation, ConversationFolder } from "@/lib/api";
import { useAuth } from "@/stores/auth";

const FOLDER_COLORS = [
  "#ef4444",
  "#f97316",
  "#eab308",
  "#22c55e",
  "#06b6d4",
  "#3b82f6",
  "#8b5cf6",
  "#ec4899",
  "#f43f5e",
];

interface SidebarProps {
  conversations: Conversation[];
  folders: ConversationFolder[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onCreateFolder: (name: string, color: string | null) => void;
  onDeleteFolder: (id: string) => void;
  onMoveConversation: (conversationId: string, folderId: string | null) => void;
  onRename: (conversationId: string, title: string) => void;
  onSearch: (query: string) => Promise<Conversation[]>;
}

export default function Sidebar({
  conversations,
  folders,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onCreateFolder,
  onDeleteFolder,
  onMoveConversation,
  onRename,
  onSearch,
}: SidebarProps) {
  const { user, logout, isAdmin } = useAuth();
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [newFolderColor, setNewFolderColor] = useState<string | null>(FOLDER_COLORS[5]);
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [moveMenuOpen, setMoveMenuOpen] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Conversation[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const menuRef = useRef<HTMLDivElement>(null);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(null);
        setMoveMenuOpen(null);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const toggleFolder = (id: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const startRename = (c: Conversation) => {
    setRenamingId(c.id);
    setRenameValue(c.title ?? "");
    setMenuOpen(null);
  };

  const submitRename = () => {
    if (renamingId && renameValue.trim()) {
      onRename(renamingId, renameValue.trim());
    }
    setRenamingId(null);
    setRenameValue("");
  };

  const cancelRename = () => {
    setRenamingId(null);
    setRenameValue("");
  };

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    if (!value.trim()) {
      setSearchResults(null);
      setSearching(false);
      return;
    }
    setSearching(true);
    searchTimerRef.current = setTimeout(async () => {
      try {
        const results = await onSearch(value.trim());
        setSearchResults(results);
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
  };

  const displayedConversations = searchResults ?? conversations;

  const isSearching = searchResults !== null;
  const unfiled = displayedConversations.filter((c) => !c.folder_id);
  const byFolder = (folderId: string) => displayedConversations.filter((c) => c.folder_id === folderId);

  const handleCreateFolder = () => {
    const name = newFolderName.trim();
    if (!name) return;
    onCreateFolder(name, newFolderColor);
    setNewFolderName("");
    setCreatingFolder(false);
    setNewFolderColor(FOLDER_COLORS[5]);
  };

  const ConversationItem = ({ c }: { c: Conversation }) => {
    if (renamingId === c.id) {
      return (
        <div
          key={c.id}
          className="group flex items-center gap-2 rounded-lg px-3 py-2 text-sm"
        >
          <MessageSquare className="h-3.5 w-3.5 shrink-0 text-tertiary" />
          <input
            autoFocus
            type="text"
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submitRename();
              if (e.key === "Escape") cancelRename();
            }}
            onBlur={submitRename}
            placeholder="Conversation title…"
            className="flex-1 rounded-md bg-hover px-2 py-1 text-xs text-primary placeholder-tertiary outline-none ring-1 ring-line focus:ring-brand"
          />
        </div>
      );
    }
    return (
    <div
      key={c.id}
      className={`group flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm transition ${
        c.id === activeId
          ? "bg-hover text-primary"
          : "text-secondary hover:bg-hover hover:text-primary"
      }`}
      onClick={() => onSelect(c.id)}
    >
      <MessageSquare className="h-3.5 w-3.5 shrink-0 text-tertiary" />
      <span className="flex-1 truncate">{c.title ?? "New conversation"}</span>
      <div className="relative">
        <button
          onClick={(e) => {
            e.stopPropagation();
            setMenuOpen(menuOpen === c.id ? null : c.id);
            setMoveMenuOpen(null);
          }}
          className="hidden shrink-0 rounded p-1 text-tertiary hover:text-primary group-hover:block"
          aria-label="Conversation options"
        >
          <MoreHorizontal className="h-3.5 w-3.5" />
        </button>
        {menuOpen === c.id && (
          <div
            ref={menuRef}
            className="animate-scale-in absolute right-0 top-7 z-50 w-44 overflow-hidden rounded-xl border border-line bg-popover py-1 shadow-2xl backdrop-blur-sm"
          >
            <button
              onClick={(e) => {
                e.stopPropagation();
                startRename(c);
              }}
              className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-xs text-secondary hover:bg-hover"
            >
              <Pencil className="h-3.5 w-3.5 text-tertiary" />
              Rename…
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setMoveMenuOpen(c.id);
                setMenuOpen(null);
              }}
              className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-xs text-secondary hover:bg-hover"
            >
              <Folder className="h-3.5 w-3.5 text-tertiary" />
              Move to folder…
            </button>
            <div className="my-1 h-px bg-line" />
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(c.id);
                setMenuOpen(null);
              }}
              className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-xs text-danger hover:bg-danger-soft"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete
            </button>
          </div>
        )}
        {moveMenuOpen === c.id && (
          <div
            ref={menuRef}
            className="animate-scale-in absolute right-0 top-7 z-50 w-48 overflow-hidden rounded-xl border border-line bg-popover py-1 shadow-2xl backdrop-blur-sm"
          >
            {folders.length === 0 && (
              <p className="px-3 py-2 text-xs text-tertiary">No folders yet</p>
            )}
            {c.folder_id && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onMoveConversation(c.id, null);
                  setMoveMenuOpen(null);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-secondary hover:bg-hover"
              >
                <MessageSquare className="h-3.5 w-3.5" />
                Unfiled
              </button>
            )}
            {folders.map((f) => (
              <button
                key={f.id}
                onClick={(e) => {
                  e.stopPropagation();
                  onMoveConversation(c.id, f.id);
                  setMoveMenuOpen(null);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-secondary hover:bg-hover"
              >
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: f.color ?? "#3b82f6" }}
                />
                {f.name}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
    );
  };

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-line/70 bg-card backdrop-blur-sm">
      <div className="flex items-center gap-3 px-4 py-4 border-b border-line/60">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-500/20">
          <Bot className="h-4 w-4 text-white" />
        </div>
        <div>
          <span className="text-sm font-semibold tracking-tight text-primary block leading-tight">
            Company Platform
          </span>
          <span className="text-[10px] text-tertiary leading-none">AI Workspace</span>
        </div>
      </div>

      <div className="px-3">
        <button
          onClick={onNew}
          className="flex w-full items-center gap-2 rounded-xl border border-line/60 bg-gradient-to-r from-brand/10 to-brand/5 px-3 py-2.5 text-sm font-medium text-secondary transition-all hover:from-brand/15 hover:to-brand/10 hover:text-primary hover:border-brand/30 shadow-sm"
        >
          <Plus className="h-4 w-4 text-brand" />
          New chat
        </button>
      </div>

      <div className="px-3 pt-3">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-tertiary" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search conversations…"
            className="w-full rounded-lg bg-hover py-1.5 pl-8 pr-7 text-xs text-primary placeholder-tertiary outline-none ring-1 ring-line focus:ring-brand"
          />
          {searchQuery && (
            <button
              onClick={() => handleSearchChange("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-tertiary hover:text-secondary"
              aria-label="Clear search"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      <nav className="mt-3 flex-1 space-y-1 overflow-y-auto px-3 pb-4">
        {/* New folder button / form */}
        {!creatingFolder ? (
          <button
            onClick={() => setCreatingFolder(true)}
            className="mb-1 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-medium text-tertiary transition hover:bg-hover hover:text-secondary"
          >
            <FolderPlus className="h-3.5 w-3.5" />
            New folder
          </button>
        ) : (
          <div className="mb-2 rounded-lg border border-line/60 bg-card p-2">
            <div className="flex items-center gap-2">
              <input
                autoFocus
                type="text"
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCreateFolder();
                  if (e.key === "Escape") {
                    setCreatingFolder(false);
                    setNewFolderName("");
                  }
                }}
                placeholder="Folder name…"
                className="flex-1 rounded-md bg-hover px-2 py-1 text-xs text-primary placeholder-tertiary outline-none ring-1 ring-line focus:ring-brand"
              />
              <button
                onClick={() => {
                  setCreatingFolder(false);
                  setNewFolderName("");
                }}
                className="rounded p-1 text-tertiary hover:text-secondary"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {FOLDER_COLORS.map((c) => (
                <button
                  key={c}
                  onClick={() => setNewFolderColor(c)}
                  className={`h-5 w-5 rounded-full transition ${newFolderColor === c ? "ring-2 ring-primary" : ""}`}
                  style={{ backgroundColor: c }}
                />
              ))}
            </div>
            <button
              onClick={handleCreateFolder}
              disabled={!newFolderName.trim()}
              className="mt-2 w-full rounded-md bg-brand px-2 py-1 text-xs font-medium text-white transition hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-40"
            >
              Create folder
            </button>
          </div>
        )}

        {/* Search results (flat list) */}
        {isSearching ? (
          <div className="space-y-0.5">
            {searching && (
              <p className="px-2 py-3 text-xs text-tertiary">Searching…</p>
            )}
            {!searching && displayedConversations.length === 0 && (
              <div className="px-3 py-10 text-center">
                <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-2xl bg-card ring-1 ring-line/60">
                  <Search className="h-5 w-5 text-tertiary" />
                </div>
                <p className="text-xs font-medium text-tertiary">No results found</p>
                <p className="mt-1 text-[11px] text-tertiary">Try a different search term</p>
              </div>
            )}
            {!searching && displayedConversations.map((c) => (
              <ConversationItem key={c.id} c={c} />
            ))}
          </div>
        ) : (
          <>
            {/* Folders */}
            {folders.map((folder) => {
              const items = byFolder(folder.id);
              const isExpanded = expandedFolders.has(folder.id);
              return (
                <div key={folder.id} className="pt-1">
                  <div className="group flex items-center gap-1.5 px-2 py-1">
                    <button
                      onClick={() => toggleFolder(folder.id)}
                      className="flex items-center gap-1.5 text-xs font-medium text-tertiary transition hover:text-secondary"
                    >
                      {isExpanded ? (
                        <ChevronDown className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5" />
                      )}
                      <span
                        className="h-2.5 w-2.5 rounded-full ring-2 ring-canvas"
                        style={{ backgroundColor: folder.color ?? "#3b82f6" }}
                      />
                      <span className="truncate">{folder.name}</span>
                      <span className="ml-1 rounded-full bg-hover px-1.5 py-0.5 text-[10px] font-semibold text-tertiary">
                        {items.length}
                      </span>
                    </button>
                    <button
                      onClick={() => onDeleteFolder(folder.id)}
                      className="ml-auto hidden rounded p-0.5 text-tertiary hover:text-danger group-hover:block"
                      aria-label="Delete folder"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                  {isExpanded && (
                    <div className="ml-4 space-y-0.5 border-l border-line/60 pl-2">
                      {items.length === 0 && (
                        <p className="px-3 py-2 text-xs text-tertiary">Empty folder</p>
                      )}
                      {items.map((c) => (
                        <ConversationItem key={c.id} c={c} />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Unfiled conversations */}
            {unfiled.length > 0 && (
              <div className="space-y-0.5 pt-1">
                {folders.length > 0 && (
                  <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-tertiary">
                    Unfiled
                  </div>
                )}
                {unfiled.map((c) => (
                  <ConversationItem key={c.id} c={c} />
                ))}
              </div>
            )}

            {conversations.length === 0 && (
              <div className="px-3 py-10 text-center">
                <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-2xl bg-card ring-1 ring-line/60">
                  <MessageSquare className="h-5 w-5 text-tertiary" />
                </div>
                <p className="text-xs font-medium text-tertiary">No conversations yet</p>
                <p className="mt-1 text-[11px] text-tertiary">Start a new chat to begin</p>
              </div>
            )}
          </>
        )}
      </nav>

      {isAdmin() && (
        <div className="flex items-center gap-2 px-3 py-2 border-t border-line/60">
          <Link
            to="/admin"
            className="flex flex-1 items-center gap-2.5 rounded-xl px-3 py-2 text-sm text-secondary hover:bg-hover hover:text-primary transition-all"
          >
            <Settings className="h-4 w-4 text-tertiary" />
            Admin Panel
          </Link>
          <ThemeToggle />
        </div>
      )}
      <div className="flex items-center gap-2.5 border-t border-line/60 px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500/20 to-violet-500/20 text-xs font-semibold uppercase text-brand ring-1 ring-line/60">
          {user?.email[0] ?? "?"}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-medium text-secondary">{user?.email}</p>
          <p className="text-[10px] uppercase tracking-wide text-tertiary">
            {user?.role}
          </p>
        </div>
        <button
          onClick={logout}
          className="rounded-lg p-1.5 text-tertiary transition hover:bg-hover hover:text-secondary"
          aria-label="Log out"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </aside>
  );
}
