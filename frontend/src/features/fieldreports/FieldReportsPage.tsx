import { useState, useMemo, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import {
  ClipboardList,
  Plus,
  Calendar,
  LayoutList,
  ChevronLeft,
  ChevronRight,
  Sun,
  Cloud,
  CloudRain,
  Snowflake,
  CloudFog,
  CloudLightning,
  Users,
  FileText,
  CheckCircle2,
  Send,
  Trash2,
  X,
  Download,
  Upload,
  FileDown,
  Loader2,
  LayoutTemplate,
} from "lucide-react";
import {
  Button,
  Card,
  Badge,
  EmptyState,
  Breadcrumb,
  ConfirmDialog,
  WideModal,
  WideModalSection,
  WideModalField,
} from '@/shared/ui';
import { useConfirm } from '@/shared/hooks/useConfirm';
import { useToastStore } from '@/stores/useToastStore';
import { useProjectContextStore } from '@/stores/useProjectContextStore';
import { todayLocalISO } from '@/shared/lib/dates';