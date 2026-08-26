from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q, Count, Max
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import ExchangeRate
from .serializers import ExchangeRateSerializer


class ExchangeRateViewSet(viewsets.ModelViewSet):
    queryset = ExchangeRate.objects.all().order_by("-date")
    serializer_class = ExchangeRateSerializer
    pagination_class = None  # Return all results for frontend filtering

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(from_currency__icontains=search) | Q(to_currency__icontains=search) | Q(source__icontains=search)
            )
        # Date range filter
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        return queryset

    # ────────────── Stats ──────────────
    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Return dashboard stats for exchange rate management."""
        today = date.today()
        today_count = ExchangeRate.objects.filter(date=today, is_deleted=False).count()
        total_count = ExchangeRate.objects.filter(is_deleted=False).count()
        latest_date = ExchangeRate.objects.filter(is_deleted=False).aggregate(
            latest=Max("date")
        )["latest"]

        # Distinct currency pairs and sources
        pairs_qs = ExchangeRate.objects.filter(is_deleted=False).values(
            "from_currency", "to_currency"
        ).order_by().distinct()
        sources_qs = ExchangeRate.objects.filter(is_deleted=False).values_list(
            "source", flat=True
        ).order_by().distinct()

        return Response({
            "today_count": today_count,
            "total_count": total_count,
            "pair_count": pairs_qs.count(),
            "source_count": len(sources_qs),
            "latest_date": latest_date.isoformat() if latest_date else None,
            "sources": list(sources_qs),
        })

    # ────────────── 一键导入当日汇率 ──────────────
    @action(detail=False, methods=["post"])
    def import_daily(self, request):
        """Import standard currency pair rates for today.
        Accepts optional body: { overwrite: bool, date: "YYYY-MM-DD", rates: [...] }
        If no body provided, uses default built-in rates.
        """
        target_date_str = (request.data or {}).get("date")
        if target_date_str:
            try:
                target_date = date.fromisoformat(target_date_str)
            except (ValueError, TypeError):
                return Response({"error": "Invalid date format, use YYYY-MM-DD"}, status=400)
        else:
            target_date = date.today()

        overwrite = (request.data or {}).get("overwrite", False)
        custom_rates = (request.data or {}).get("rates")

        if custom_rates:
            # Parse custom rates from request body
            pairs = []
            for item in custom_rates:
                pairs.append((
                    item.get("from_currency"),
                    item.get("to_currency"),
                    Decimal(str(item.get("rate", 0))),
                    item.get("source", "Manual"),
                ))
        else:
            # Default built-in rates: USD/CNY/EUR/GBP/JPY/HKD cross pairs
            pairs = [
                ("USD", "CNY", Decimal("7.2456"), "Reuters"),
                ("CNY", "USD", Decimal("0.1380"), "Reuters"),
                ("USD", "EUR", Decimal("0.9185"), "Reuters"),
                ("EUR", "USD", Decimal("1.0887"), "Reuters"),
                ("USD", "GBP", Decimal("0.7892"), "Reuters"),
                ("GBP", "USD", Decimal("1.2671"), "Reuters"),
                ("USD", "JPY", Decimal("149.35"), "Reuters"),
                ("JPY", "USD", Decimal("0.006696"), "Reuters"),
                ("USD", "HKD", Decimal("7.8124"), "Reuters"),
                ("HKD", "USD", Decimal("0.1280"), "Reuters"),
                ("CNY", "HKD", Decimal("1.0782"), "Reuters"),
                ("HKD", "CNY", Decimal("0.9275"), "Reuters"),
                ("EUR", "CNY", Decimal("7.8862"), "Reuters"),
                ("EUR", "GBP", Decimal("0.8594"), "Reuters"),
                ("EUR", "JPY", Decimal("162.58"), "Reuters"),
                ("GBP", "CNY", Decimal("9.1753"), "Reuters"),
                ("GBP", "JPY", Decimal("189.12"), "Reuters"),
                ("GBP", "HKD", Decimal("9.8937"), "Reuters"),
                ("JPY", "CNY", Decimal("0.04852"), "Reuters"),
                ("HKD", "JPY", Decimal("19.12"), "Reuters"),
            ]

        created = 0
        updated = 0
        for f_cur, t_cur, rate_val, src in pairs:
            if overwrite:
                obj, c = ExchangeRate.objects.update_or_create(
                    date=target_date,
                    from_currency=f_cur,
                    to_currency=t_cur,
                    defaults={"rate": rate_val, "source": src, "is_deleted": False},
                )
                if c:
                    created += 1
                else:
                    updated += 1
            else:
                obj, c = ExchangeRate.objects.get_or_create(
                    date=target_date,
                    from_currency=f_cur,
                    to_currency=t_cur,
                    defaults={"rate": rate_val, "source": src},
                )
                if c:
                    created += 1

        msg = f"Imported {created} new rates"
        if overwrite and updated:
            msg += f", updated {updated} existing rates"
        msg += f" for {target_date.isoformat()}"

        return Response({
            "created": created,
            "updated": updated if overwrite else 0,
            "date": target_date.isoformat(),
            "message": msg,
        })

    # ────────────── 同步实时行情 ──────────────
    @action(detail=False, methods=["post"])
    def sync_realtime(self, request):
        """Sync real-time exchange rates from configured FX provider."""
        from .providers import get_fx_provider

        today = date.today()
        source = (request.data or {}).get("source", "Bloomberg")
        try:
            provider = get_fx_provider()
            rates = provider.fetch_rates(source=source)
        except NotImplementedError as e:
            return Response({"error": str(e)}, status=501)

        created = 0
        updated = 0
        for item in rates:
            obj, c = ExchangeRate.objects.update_or_create(
                date=today,
                from_currency=item["from_currency"],
                to_currency=item["to_currency"],
                defaults={"rate": item["rate"], "source": item.get("source", source), "is_deleted": False},
            )
            if c:
                created += 1
            else:
                updated += 1

        return Response({
            "created": created,
            "updated": updated,
            "source": source,
            "date": today.isoformat(),
            "message": f"Synced {created + updated} rates from {source} for {today.isoformat()}",
        })

    @action(detail=False, methods=["post"], url_path="batch-update")
    def batch_update(self, request):
        """前端兼容别名 — 无 rates 时走 import_daily，有 rates 时走 batch_create。"""
        if (request.data or {}).get("rates"):
            return self.batch_create(request)
        return self.import_daily(request)

    @action(detail=False, methods=["get"])
    def latest(self, request):
        """查询最新汇率。Query: from_currency, to_currency"""
        from_cur = (request.query_params.get("from_currency") or request.query_params.get("base") or "").upper()
        to_cur = (request.query_params.get("to_currency") or request.query_params.get("quote") or "").upper()
        qs = ExchangeRate.objects.filter(is_deleted=False).order_by("-date")
        if from_cur:
            qs = qs.filter(from_currency=from_cur)
        if to_cur:
            qs = qs.filter(to_currency=to_cur)
        rate = qs.first()
        if not rate:
            return Response({"detail": "Rate not found"}, status=404)
        return Response(ExchangeRateSerializer(rate).data)

    @action(detail=False, methods=["post"])
    def convert(self, request):
        """按最新汇率换算。Body: { from_currency, to_currency, amount }"""
        from_cur = str((request.data or {}).get("from_currency") or "").upper()
        to_cur = str((request.data or {}).get("to_currency") or "").upper()
        try:
            amount = Decimal(str((request.data or {}).get("amount", 0)))
        except Exception:
            return Response({"error": "Invalid amount"}, status=400)
        if not from_cur or not to_cur:
            return Response({"error": "from_currency and to_currency required"}, status=400)
        if from_cur == to_cur:
            return Response({"from_currency": from_cur, "to_currency": to_cur, "amount": str(amount), "rate": "1", "converted": str(amount)})
        rate_obj = ExchangeRate.objects.filter(
            from_currency=from_cur, to_currency=to_cur, is_deleted=False
        ).order_by("-date").first()
        if not rate_obj:
            return Response({"error": "Rate not found"}, status=404)
        converted = (amount * rate_obj.rate).quantize(Decimal("0.01"))
        return Response({
            "from_currency": from_cur,
            "to_currency": to_cur,
            "amount": str(amount),
            "rate": str(rate_obj.rate),
            "converted": str(converted),
            "date": rate_obj.date.isoformat(),
        })

    # ────────────── 批量录入 ──────────────
    @action(detail=False, methods=["post"])
    def batch_create(self, request):
        """Batch create multiple exchange rates at once.
        Body: { rates: [{ from_currency, to_currency, rate, date, source }, ...] }
        """
        rates_data = (request.data or {}).get("rates", [])
        if not rates_data:
            return Response({"error": "No rates data provided"}, status=400)

        created = 0
        errors = []
        for idx, item in enumerate(rates_data):
            item_date_str = item.get("date") or date.today().isoformat()
            try:
                item_date = date.fromisoformat(item_date_str)
            except (ValueError, TypeError):
                errors.append(f"Row {idx + 1}: Invalid date format")
                continue

            serializer = ExchangeRateSerializer(data={
                "date": item_date,
                "from_currency": item.get("from_currency", "").upper(),
                "to_currency": item.get("to_currency", "").upper(),
                "rate": item.get("rate"),
                "source": item.get("source", "Manual"),
            })
            if serializer.is_valid():
                serializer.save()
                created += 1
            else:
                errors.append(f"Row {idx + 1}: {serializer.errors}")

        return Response({
            "created": created,
            "errors": errors,
            "message": f"Created {created} rates, {len(errors)} errors" if errors else f"Successfully created {created} rates",
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="import-csv")
    def import_csv(self, request):
        """CSV 批量导入。格式: date,from_currency,to_currency,rate,source

        multipart: file=<csv> 或 body.text=<csv content>
        """
        import csv
        import io

        content = ""
        upload = request.FILES.get("file")
        if upload:
            content = upload.read().decode("utf-8-sig")
        else:
            content = (request.data or {}).get("text") or (request.data or {}).get("csv") or ""

        if not content.strip():
            return Response({"error": "CSV content required"}, status=400)

        reader = csv.reader(io.StringIO(content.strip()))
        created = 0
        updated = 0
        errors = []
        for idx, row in enumerate(reader, start=1):
            if not row or all(not str(c).strip() for c in row):
                continue
            # skip header
            if idx == 1 and str(row[0]).lower().strip() in ("date", "日期"):
                continue
            if len(row) < 4:
                errors.append(f"Row {idx}: need date,from,to,rate[,source]")
                continue
            try:
                item_date = date.fromisoformat(str(row[0]).strip())
                from_cur = str(row[1]).strip().upper()
                to_cur = str(row[2]).strip().upper()
                rate_val = Decimal(str(row[3]).strip())
                source = str(row[4]).strip() if len(row) > 4 and str(row[4]).strip() else "Manual"
            except Exception as e:
                errors.append(f"Row {idx}: {e}")
                continue

            obj, c = ExchangeRate.objects.update_or_create(
                date=item_date,
                from_currency=from_cur,
                to_currency=to_cur,
                defaults={"rate": rate_val, "source": source, "is_deleted": False},
            )
            if c:
                created += 1
            else:
                updated += 1

        return Response({
            "created": created,
            "updated": updated,
            "errors": errors,
            "message": f"CSV import: created {created}, updated {updated}, errors {len(errors)}",
        })
