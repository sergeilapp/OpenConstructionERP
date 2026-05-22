/**
 * BIMPage — Premium BIM Hub with immersive 3D viewport and polished light UI.
 *
 * Layout:
 *  - Clean light header with stats + actions
 *  - Full-height 3D viewport
 *  - Glass-morphism model filmstrip at the bottom
 *  - Slide-in upload panel from right
 *  - Professional landing page when no models exist
 *
 * Route: /projects/:projectId/bim  or  /bim
 */

import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import clsx from "clsx";
import { useTranslation } from "react-i18next";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  ChevronRight,
  Loader2,
  FolderOpen,
  Link2,
  Upload,
  Database,
  FileBox,
  FileUp,
  X,
  CheckCircle2,
  AlertCircle,
  ChevronUp,
  CalendarDays,
  Trash2,
  RotateCcw,
  DownloadCloud,
  Eye,
  Layers,
  AlertTriangle,
  UploadCloud,
  Sparkles,
  Building2,
  Ruler,
  Globe2,
  ArrowRight,
  Plus,
  Cuboid,
  SlidersHorizontal,
  ClipboardList,
  ShieldCheck,
  LayoutGrid,
  Maximize2,
  Package,
  GitCompare,
} from "lucide-react";
import { Badge, EmptyState, Breadcrumb, ConfirmDialog } from "@/shared/ui";
import { useConfirm } from "@/shared/hooks/useConfirm";
import { BIMViewer } from "@/shared/ui/BIMViewer";
import type { BIMElementData, BIMModelData } from "@/shared/ui/BIMViewer";
import {
  parseBIMUrlState,
  serializeBIMUrlState,
  BIM_URL_STATE_KEYS,
} from '@/shared/ui/BIMViewer/urlState';
import BIMFilterGroupsPanel from './BIMFilterGroupsPanel';
import BIMRightPanelTabs from './BIMRightPanelTabs';
import PropertySearchPanel from './PropertySearchPanel';
import BIMDiffPanel from './BIMDiffPanel';
import type { DiffChangeType } from './diffGrouping';
import ElementAssetCard from './ElementAssetCard';
import BIMSnapshotsPopover from './BIMSnapshotsPopover';
import { useBIMViewerStore } from '@/stores/useBIMViewerStore';
import { BIMConverterStatusBanner } from './BIMConverterStatusBanner';
import { InstallConverterPrompt } from './InstallConverterPrompt';
import AddToBOQModal from './AddToBOQModal';
import SaveGroupModal from './SaveGroupModal';
import CreateTaskFromBIMModal from './CreateTaskFromBIMModal';
import LinkDocumentToBIMModal from './LinkDocumentToBIMModal';
import LinkActivityToBIMModal from './LinkActivityToBIMModal';
import LinkRequirementToBIMModal from './LinkRequirementToBIMModal';
import type { BIMGroupFilterCriteria } from './api';
import { Filter, Search } from 'lucide-react';
import { SmartViewsPanel } from '@/features/smart_views/SmartViewsPanel';
import { useSmartViewState } from '@/features/smart_views/useSmartViewState';
import { useProjectContextStore } from '@/stores/useProjectContextStore';
import { useToastStore } from '@/stores/useToastStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { useBIMLinkSelectionStore } from '@/stores/useBIMLinkSelectionStore';
import { useBIMUploadStore, type BIMUploadJob } from '@/stores/useBIMUploadStore';
import { apiGet } from '@/shared/lib/api';