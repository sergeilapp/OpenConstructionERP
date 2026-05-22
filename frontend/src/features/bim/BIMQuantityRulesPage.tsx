/**
 * BIMQuantityRulesPage — rule-based bulk linking of BIM elements to BOQ positions.
 *
 * Route: /bim/rules
 *
 * Lets the user define patterns like "category=Walls AND storey=01 Entry Level"
 * and map them to a BOQ position (either existing or auto-created). Applying a
 * rule creates `BOQElementLink` rows in bulk against a selected BIM model.
 *
 * Reads the active project from the global project-context store.
 */

import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Pencil,
  Trash2,
  Copy,
  Play,
  Eye,
  SlidersHorizontal,
  X,
  Check,
  AlertCircle,
  Loader2,
  Boxes,
  BookOpen,
  Sparkles,
  ChevronRight,
  ClipboardCheck,
  Shield,
  Search,
  Upload,
  Download,
  CheckCircle2,
  LayoutPanelTop,
  Layers3,
  DoorOpen,
  AppWindow,
  Flame,
  Thermometer,
  Construction,
  type LucideIcon,
} from "lucide-react";
import clsx from "clsx";

import { Badge, ConfirmDialog, EmptyState } from "@/shared/ui";
import { apiGet } from "@/shared/lib/api";
import { FolderOpen } from "lucide-react";
import BIMRequirementsImport from "./BIMRequirementsImport";
import { useProjectContextStore } from "@/stores/useProjectContextStore";
import { useToastStore } from "@/stores/useToastStore";
import { RulePackLibrary } from '@/features/bim_requirements/RulePackLibrary';