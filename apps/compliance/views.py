"""Compliance API views"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import SanctionList, SanctionScanRecord, SanctionHitDetail
from .serializers import (
    SanctionListSerializer, SanctionScanRecordSerializer, SanctionHitDetailSerializer,
)
from .services import scan_entity
from apps.rbac.authentication import JWTAuthentication


class SanctionListViewSet(viewsets.ModelViewSet):
    """制裁名单管理"""
    authentication_classes = [JWTAuthentication]
    queryset = SanctionList.objects.all()
    serializer_class = SanctionListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["list_type", "risk_level", "is_active", "entity_type"]
    search_fields = ["entity_name", "alias_names", "id_number"]

    @action(detail=False, methods=["get"])
    def list_types(self, request):
        """返回所有已导入的制裁名单类型及数量（用于前端下拉框动态展示）"""
        from django.db.models import Count
        qs = SanctionList.objects.filter(is_active=True).values("list_type").annotate(count=Count("id")).order_by("list_type")
        type_labels = dict(SanctionList.LIST_TYPES)
        result = []
        for item in qs:
            lt = item["list_type"]
            result.append({
                "value": lt,
                "label": type_labels.get(lt, lt),
                "count": item["count"],
            })
        return Response({
            "types": result,
            "total": SanctionList.objects.filter(is_active=True).count(),
        })

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """返回全量制裁名单统计（按风险等级 + 按名单类型交叉统计）
        前端统计卡片使用此端点，而非仅基于当前页数据计算。
        """
        from django.db.models import Count, Q

        base_qs = SanctionList.objects.filter(is_active=True)

        # 按风险等级
        by_risk = {
            "HIGH": base_qs.filter(risk_level="HIGH").count(),
            "MEDIUM": base_qs.filter(risk_level="MEDIUM").count(),
            "LOW": base_qs.filter(risk_level="LOW").count(),
        }

        # 按名单类型
        by_type = {}
        type_labels = dict(SanctionList.LIST_TYPES)
        for item in base_qs.values("list_type").annotate(count=Count("id")).order_by("-count"):
            lt = item["list_type"]
            by_type[lt] = {
                "label": type_labels.get(lt, lt),
                "count": item["count"],
                "high": base_qs.filter(list_type=lt, risk_level="HIGH").count(),
            }

        # 按实体类型
        by_entity = {}
        entity_labels = dict(SanctionList.ENTITY_TYPES) if hasattr(SanctionList, "ENTITY_TYPES") else {}
        for item in base_qs.values("entity_type").annotate(count=Count("id")).order_by("-count"):
            et = item["entity_type"]
            by_entity[et] = {
                "label": entity_labels.get(et, et),
                "count": item["count"],
            }

        return Response({
            "total": base_qs.count(),
            "by_risk": by_risk,
            "by_type": by_type,
            "by_entity": by_entity,
        })

    @action(detail=False, methods=["post"])
    def import_builtin(self, request):
        """导入制裁名单数据

        优先尝试使用真实数据文件（import_real_sanctions 命令），
        如果文件不存在则回退到内置样本数据（旧命令）。
        """
        import io
        import sys
        import os
        from django.core.management import call_command

        source = request.data.get("source", "ALL")
        reset = request.data.get("reset", False)

        # 真实数据文件默认路径（用户下载目录）
        default_un = os.path.expanduser("~/Downloads/consolidatedLegacyByPRN.html")
        default_ofac = os.path.expanduser("~/Downloads/sdn_enhanced.zip")

        un_available = os.path.exists(default_un)
        ofac_available = os.path.exists(default_ofac)

        # 请求中指定的自定义文件路径
        un_file = request.data.get("un_file", default_un if un_available else None)
        ofac_file = request.data.get("ofac_file", default_ofac if ofac_available else None)

        results = {}
        use_real = (un_file and os.path.exists(un_file)) or (ofac_file and os.path.exists(ofac_file))

        if use_real:
            # 使用新的真实数据导入命令
            try:
                cmd_args = []
                if source in ("UN", "ALL") and un_file:
                    cmd_args.append(f"--un-file={un_file}")
                if source in ("OFAC", "ALL") and ofac_file:
                    cmd_args.append(f"--ofac-file={ofac_file}")
                if source == "UN" and un_file:
                    cmd_args.append("--only-un")
                elif source == "OFAC" and ofac_file:
                    cmd_args.append("--only-ofac")
                if reset:
                    cmd_args.append("--reset")

                if not cmd_args:
                    results["error"] = "未找到可导入的数据文件"
                else:
                    output = io.StringIO()
                    err_out = io.StringIO()
                    old_stdout, old_stderr = sys.stdout, sys.stderr
                    sys.stdout = output
                    sys.stderr = err_out
                    try:
                        call_command("import_real_sanctions", *cmd_args)
                    finally:
                        sys.stdout = old_stdout
                        sys.stderr = old_stderr

                    results["source"] = "real"
                    results["status"] = "success"
                    results["output"] = output.getvalue()[-2000:]  # 截取最后2000字符
            except Exception as e:
                results["source"] = "real"
                results["status"] = "error"
                results["message"] = str(e)
        else:
            # 回退到内置样本数据
            if source in ("OFAC", "ALL"):
                try:
                    output = io.StringIO()
                    old_stdout, old_stderr = sys.stdout, sys.stderr
                    sys.stdout = output
                    sys.stderr = io.StringIO()
                    try:
                        call_command("import_ofac_sdn", use_builtin=True, reset=reset, max_entries=500)
                    finally:
                        sys.stdout = old_stdout
                        sys.stderr = old_stderr
                    results["OFAC"] = {"status": "success", "output": output.getvalue()}
                except Exception as e:
                    results["OFAC"] = {"status": "error", "message": str(e)}

            if source in ("UN", "ALL"):
                try:
                    output2 = io.StringIO()
                    old_stdout, old_stderr = sys.stdout, sys.stderr
                    sys.stdout = output2
                    sys.stderr = io.StringIO()
                    try:
                        call_command("import_un_sanctions", reset=reset)
                    finally:
                        sys.stdout = old_stdout
                        sys.stderr = old_stderr
                    results["UN"] = {"status": "success", "output": output2.getvalue()}
                except Exception as e:
                    results["UN"] = {"status": "error", "message": str(e)}

        return Response({
            "results": results,
            "total_ofac": SanctionList.objects.filter(list_type="OFAC", is_active=True).count(),
            "total_un": SanctionList.objects.filter(list_type="UN", is_active=True).count(),
            "total_all": SanctionList.objects.filter(is_active=True).count(),
        })

class SanctionScanRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """制裁扫描记录查询"""
    authentication_classes = [JWTAuthentication]
    queryset = SanctionScanRecord.objects.all().prefetch_related("hits__sanction_entry")
    serializer_class = SanctionScanRecordSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["scan_type", "status"]
    search_fields = ["scan_no", "target_name"]
    ordering = ["-created_at"]

    @action(detail=False, methods=["post"])
    def scan(self, request):
        """执行制裁扫描"""
        target_name = request.data.get("target_name", "")
        target_type = request.data.get("target_type", "PERSON")
        target_id = request.data.get("target_id", "")
        if not target_name:
            return Response({"error": "target_name is required"}, status=status.HTTP_400_BAD_REQUEST)
        is_clear, scan_record = scan_entity(target_name, target_type, target_id)
        serializer = self.get_serializer(scan_record)
        return Response(serializer.data)


class SanctionHitDetailViewSet(viewsets.ReadOnlyModelViewSet):
    """制裁命中明细查询"""
    authentication_classes = [JWTAuthentication]
    queryset = SanctionHitDetail.objects.all()
    serializer_class = SanctionHitDetailSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["scan_record__scan_no", "is_resolved", "resolution"]

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        """处理命中记录"""
        hit = self.get_object()
        resolution = request.data.get("resolution", "FALSE_POSITIVE")
        hit.resolution = resolution
        hit.is_resolved = True
        hit.resolved_by = request.data.get("resolved_by", "")
        hit.remark = request.data.get("remark", "")
        from django.utils import timezone
        hit.resolved_at = timezone.now()
        hit.save()
        return Response(SanctionHitDetailSerializer(hit).data)
