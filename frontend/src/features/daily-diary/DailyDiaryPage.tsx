import { useState, useMemo, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import {
  Calendar,
  BookOpen,
  Archive,
  Plus,
  Lock,
  Cloud,
  Camera,
  Plane,
  Scan,
  FileSignature,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  Trash2,
  ArrowRight,
  X,
} from "lucide-react";
import {
  Button,
  Card,
  Badge,
  EmptyState,
  Breadcrumb,
  SkeletonTable,
  WideModal,
  WideModalSection,
  WideModalField,
} from '@/shared/ui';
import { DateDisplay } from '@/shared/ui/DateDisplay';
import { useToastStore } from '@/stores/useToastStore';
import { useProjectContextStore } from '@/stores/useProjectContextStore';
import { getErrorMessage } from '@/shared/lib/api';
import { todayLocalISO, isoDateFromLocal, nowLocalISO } from '@/shared/lib/dates';
import { projectsApi } from '@/features/projects/api';