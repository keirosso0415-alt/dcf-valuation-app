"""
DCF Valuation Model - Core Logic
================================
A株式会社 DCFモデルのPython実装
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Literal
from enum import Enum
import numpy as np
import pandas as pd


class Scenario(Enum):
    BULL = "強気"
    BASE = "ベース"
    BEAR = "弱気"


@dataclass
class Assumptions:
    """前提条件"""
    # シナリオ
    scenario: Scenario = Scenario.BASE
    
    # 予測期間
    projection_years: int = 5
    base_year: int = 2022
    
    # 収益予測（シナリオ別）
    revenue_growth: Dict[Scenario, float] = field(default_factory=lambda: {
        Scenario.BULL: 0.15,
        Scenario.BASE: 0.10,
        Scenario.BEAR: 0.05
    })
    
    # コスト構造
    cogs_ratio: float = 0.625          # 売上原価率
    sga_ratio: float = 0.28            # 販管費率
    depreciation_ratio: float = 0.14   # 減価償却/期初固定資産
    capex_ratio: float = 0.04          # 設備投資/売上
    
    # 運転資本
    receivable_days: float = 77.0      # 売上債権回転日数
    inventory_days: float = 44.0       # 棚卸資産回転日数
    payable_days: float = 122.0        # 仕入債務回転日数
    
    # 税率
    effective_tax_rate: float = 0.295  # 実効税率
    marginal_tax_rate: float = 0.309   # 限界税率
    
    # WACC構成要素
    risk_free_rate: float = 0.0087     # リスクフリーレート
    unlevered_beta: float = 0.90       # アンレバードβ
    target_de_ratio: float = 0.50      # 目標D/Eレシオ
    equity_risk_premium: float = 0.07  # 株式リスクプレミアム
    size_premium: float = 0.02         # サイズプレミアム
    cost_of_debt: float = 0.03         # 負債コスト
    
    # ターミナルバリュー
    terminal_growth_rate: float = 0.02  # 永久成長率
    exit_ebitda_multiple: float = 8.0   # Exit EV/EBITDA
    
    # 収益認識タイミング
    mid_year_convention: bool = True    # 年央主義
    
    @property
    def current_revenue_growth(self) -> float:
        return self.revenue_growth[self.scenario]


@dataclass
class HistoricalData:
    """実績データ（基準年: 2022年）"""
    revenue: float = 2080000            # 売上収益（仮定）
    ebitda: float = 374400              # EBITDA
    ebit: float = 291200                # EBIT
    net_income: float = 171104          # 当期純利益
    
    # B/S項目（2022年実績）
    cash: float = 58054                 # 現金及び現金同等物
    receivables: float = 433436         # 営業債権及びその他の債権
    inventory: float = 155938           # 棚卸資産
    other_current_assets: float = 164995  # その他流動資産
    ppe: float = 717914                 # 有形固定資産
    intangibles: float = 1538679        # のれん及び無形資産
    equity_investments: float = 4846    # 持分法投資
    other_non_current: float = 272952   # その他非流動資産
    
    payables: float = 433582            # 営業債務及びその他の債務
    short_term_debt: float = 98208      # 短期借入金
    long_term_debt: float = 1245938     # 社債及び借入金
    other_current_liabilities: float = 229627  # 未払法人所得税等 + その他流動負債
    deferred_tax_liabilities: float = 156780  # 繰延税金負債
    other_non_current_liabilities: float = 29934  # その他非流動負債
    minority_interest: float = 7612     # 非支配持分
    
    shares_outstanding: float = 483.585  # 希薄化後株式数（百万株）
    current_stock_price: float = 4533    # 現在株価（参考）


@dataclass
class ProjectionPeriod:
    """単年度予測"""
    year: int
    label: str  # "2023", "2024", etc.
    
    # P/L
    revenue: float = 0
    cogs: float = 0
    gross_profit: float = 0
    sga: float = 0
    other_operating_income: float = 0
    other_operating_expense: float = 0
    ebitda: float = 0
    depreciation: float = 0
    ebit: float = 0
    interest_expense: float = 0
    interest_income: float = 0
    ebt: float = 0
    tax: float = 0
    net_income: float = 0
    
    # B/S
    cash: float = 0
    receivables: float = 0
    inventory: float = 0
    other_current_assets: float = 0
    ppe: float = 0
    intangibles: float = 0
    equity_investments: float = 0
    
    payables: float = 0
    short_term_debt: float = 0
    long_term_debt: float = 0
    
    # C/F & FCF
    capex: float = 0
    delta_nwc: float = 0
    fcf: float = 0
    
    # DCF
    discount_period: float = 0
    discount_factor: float = 0
    pv_fcf: float = 0


class DCFModel:
    """DCFバリュエーションモデル"""
    
    def __init__(
        self,
        assumptions: Optional[Assumptions] = None,
        historical: Optional[HistoricalData] = None
    ):
        self.assumptions = assumptions or Assumptions()
        self.historical = historical or HistoricalData()
        self.projections: List[ProjectionPeriod] = []
        self._calculate()
    
    def _calculate(self):
        """全計算を実行"""
        self._project_financials()
        self._calculate_fcf()
        self._calculate_discount_factors()
        self._calculate_dcf()
    
    def _project_financials(self):
        """財務三表の予測"""
        self.projections = []
        assumptions = self.assumptions
        hist = self.historical
        
        prev_revenue = hist.revenue
        prev_ppe = hist.ppe
        
        # 基準年の運転資本比率を計算
        base_receivables_ratio = hist.receivables / hist.revenue
        base_inventory_ratio = hist.inventory / hist.revenue
        base_payables_ratio = hist.payables / hist.revenue
        
        prev_nwc = hist.receivables + hist.inventory - hist.payables
        
        growth = assumptions.current_revenue_growth
        
        for i in range(assumptions.projection_years):
            year = assumptions.base_year + i + 1
            period = ProjectionPeriod(
                year=year,
                label=f"{year}"
            )
            
            # P/L
            period.revenue = prev_revenue * (1 + growth)
            period.cogs = -period.revenue * assumptions.cogs_ratio
            period.gross_profit = period.revenue + period.cogs
            period.sga = -period.revenue * assumptions.sga_ratio
            period.depreciation = -prev_ppe * assumptions.depreciation_ratio
            period.ebitda = period.gross_profit + period.sga
            period.ebit = period.ebitda + period.depreciation
            period.tax = -period.ebit * assumptions.effective_tax_rate if period.ebit > 0 else 0
            period.net_income = period.ebit + period.tax
            
            # B/S - 運転資本（対売上比率を維持）
            period.receivables = period.revenue * base_receivables_ratio
            period.inventory = period.revenue * base_inventory_ratio
            period.payables = period.revenue * base_payables_ratio
            
            current_nwc = period.receivables + period.inventory - period.payables
            period.delta_nwc = current_nwc - prev_nwc
            
            # B/S - 固定資産
            period.capex = period.revenue * assumptions.capex_ratio
            period.ppe = prev_ppe + period.capex + period.depreciation
            period.intangibles = hist.intangibles  # 一定と仮定
            
            self.projections.append(period)
            
            # 次期への繰越
            prev_revenue = period.revenue
            prev_ppe = period.ppe
            prev_nwc = current_nwc
    
    def _calculate_fcf(self):
        """フリーキャッシュフロー計算"""
        for period in self.projections:
            # NOPAT = EBIT × (1 - 税率)
            nopat = period.ebit * (1 - self.assumptions.effective_tax_rate)
            
            # FCF = NOPAT + 減価償却 - 設備投資 - Δ運転資本
            period.fcf = (
                nopat
                - period.depreciation  # 減価償却はマイナスで入っているので引く
                - period.capex
                - period.delta_nwc
            )
    
    def _calculate_discount_factors(self):
        """割引係数の計算"""
        wacc = self.wacc
        
        for i, period in enumerate(self.projections):
            # 割引期間（年央主義の場合は0.5年短縮）
            if self.assumptions.mid_year_convention:
                period.discount_period = i + 1 - 0.5
            else:
                period.discount_period = i + 1
            
            # 割引係数
            period.discount_factor = 1 / ((1 + wacc) ** period.discount_period)
            
            # FCF現在価値
            period.pv_fcf = period.fcf * period.discount_factor
    
    def _calculate_dcf(self):
        """DCFバリュエーション計算"""
        pass  # 結果はプロパティで取得
    
    # ========== WACC計算 ==========
    
    @property
    def levered_beta(self) -> float:
        """レバードβ = アンレバードβ × [1 + D/E × (1-t)]"""
        a = self.assumptions
        return a.unlevered_beta * (1 + a.target_de_ratio * (1 - a.effective_tax_rate))
    
    @property
    def cost_of_equity(self) -> float:
        """株主資本コスト = Rf + β × ERP + Size Premium"""
        a = self.assumptions
        return (
            a.risk_free_rate
            + self.levered_beta * a.equity_risk_premium
            + a.size_premium
        )
    
    @property
    def after_tax_cost_of_debt(self) -> float:
        """税引後負債コスト"""
        a = self.assumptions
        return a.cost_of_debt * (1 - a.effective_tax_rate)
    
    @property
    def wacc(self) -> float:
        """加重平均資本コスト"""
        a = self.assumptions
        weight_equity = 1 / (1 + a.target_de_ratio)
        weight_debt = 1 - weight_equity
        
        return (
            self.cost_of_equity * weight_equity
            + self.after_tax_cost_of_debt * weight_debt
        )
    
    # ========== DCF結果 ==========
    
    @property
    def sum_pv_fcf(self) -> float:
        """FCF現在価値合計"""
        return sum(p.pv_fcf for p in self.projections)
    
    @property
    def terminal_fcf(self) -> float:
        """最終年度FCF"""
        return self.projections[-1].fcf
    
    @property
    def terminal_ebitda(self) -> float:
        """最終年度EBITDA"""
        return self.projections[-1].ebitda
    
    def terminal_value_perpetuity(self, growth_rate: Optional[float] = None) -> float:
        """ターミナルバリュー（永久成長率法）"""
        g = growth_rate if growth_rate is not None else self.assumptions.terminal_growth_rate
        return self.terminal_fcf * (1 + g) / (self.wacc - g)
    
    def terminal_value_exit_multiple(self, multiple: Optional[float] = None) -> float:
        """ターミナルバリュー（Exit Multiple法）"""
        m = multiple if multiple is not None else self.assumptions.exit_ebitda_multiple
        return self.terminal_ebitda * m
    
    def pv_terminal_value(self, method: Literal["perpetuity", "exit_multiple"] = "perpetuity") -> float:
        """ターミナルバリューの現在価値"""
        if method == "perpetuity":
            tv = self.terminal_value_perpetuity()
        else:
            tv = self.terminal_value_exit_multiple()
        
        # 最終年度の割引係数を使用
        return tv * self.projections[-1].discount_factor
    
    def enterprise_value(self, method: Literal["perpetuity", "exit_multiple"] = "perpetuity") -> float:
        """企業価値"""
        return self.sum_pv_fcf + self.pv_terminal_value(method)
    
    @property
    def net_debt(self) -> float:
        """ネットデット"""
        hist = self.historical
        return (
            hist.short_term_debt
            + hist.long_term_debt
            - hist.cash
            - hist.equity_investments
        )
    
    def equity_value(self, method: Literal["perpetuity", "exit_multiple"] = "perpetuity") -> float:
        """株式価値"""
        return (
            self.enterprise_value(method)
            - self.net_debt
            - self.historical.minority_interest
        )
    
    def price_per_share(self, method: Literal["perpetuity", "exit_multiple"] = "perpetuity") -> float:
        """理論株価"""
        return self.equity_value(method) / self.historical.shares_outstanding
    
    def upside(self, method: Literal["perpetuity", "exit_multiple"] = "perpetuity") -> float:
        """アップサイド（%）"""
        theoretical = self.price_per_share(method)
        current = self.historical.current_stock_price
        return (theoretical - current) / current
    
    # ========== クロスチェック ==========
    
    def implied_exit_multiple(self) -> float:
        """インプライドEV/EBITDA（永久成長率法から逆算）"""
        tv = self.terminal_value_perpetuity()
        return tv / self.terminal_ebitda
    
    def implied_perpetual_growth(self) -> float:
        """インプライド永久成長率（Exit Multiple法から逆算）"""
        tv = self.terminal_value_exit_multiple()
        # TV = FCF × (1+g) / (WACC - g) を g について解く
        # g = (TV × WACC - FCF) / (TV + FCF)
        fcf = self.terminal_fcf
        return (tv * self.wacc - fcf) / (tv + fcf)
    
    @property
    def tv_percentage_perpetuity(self) -> float:
        """TV/EV比率（永久成長率法）"""
        ev = self.enterprise_value("perpetuity")
        pv_tv = self.pv_terminal_value("perpetuity")
        return pv_tv / ev if ev > 0 else 0
    
    @property
    def tv_percentage_exit_multiple(self) -> float:
        """TV/EV比率（Exit Multiple法）"""
        ev = self.enterprise_value("exit_multiple")
        pv_tv = self.pv_terminal_value("exit_multiple")
        return pv_tv / ev if ev > 0 else 0
    
    # ========== マルチプル法 ==========
    
    @property
    def market_cap(self) -> float:
        """時価総額"""
        return self.historical.current_stock_price * self.historical.shares_outstanding
    
    @property
    def market_ev(self) -> float:
        """市場ベースEV（時価総額 + ネットデット）"""
        return self.market_cap + self.net_debt + self.historical.minority_interest
    
    @property
    def market_ev_ebitda(self) -> float:
        """市場ベースEV/EBITDA"""
        if self.historical.ebitda > 0:
            return self.market_ev / self.historical.ebitda
        return 0
    
    @property
    def market_per(self) -> float:
        """市場PER"""
        if self.historical.net_income > 0:
            return self.market_cap / self.historical.net_income
        return 0
    
    def multiple_valuation(
        self,
        ev_ebitda_multiple: Optional[float] = None,
        per_multiple: Optional[float] = None
    ) -> Dict:
        """
        マルチプル法によるバリュエーション
        
        Parameters
        ----------
        ev_ebitda_multiple : float, optional
            EV/EBITDA倍率（指定なしの場合は市場倍率を使用）
        per_multiple : float, optional
            PER倍率（指定なしの場合は市場倍率を使用）
        
        Returns
        -------
        dict
            各手法による株式価値と理論株価
        """
        hist = self.historical
        
        # EV/EBITDA法
        ev_ebitda = ev_ebitda_multiple if ev_ebitda_multiple else self.market_ev_ebitda
        ev_from_ebitda = hist.ebitda * ev_ebitda
        equity_from_ebitda = ev_from_ebitda - self.net_debt - hist.minority_interest
        price_from_ebitda = equity_from_ebitda / hist.shares_outstanding if hist.shares_outstanding > 0 else 0
        
        # PER法
        per = per_multiple if per_multiple else self.market_per
        equity_from_per = hist.net_income * per
        price_from_per = equity_from_per / hist.shares_outstanding if hist.shares_outstanding > 0 else 0
        
        return {
            "ev_ebitda": {
                "multiple": ev_ebitda,
                "ebitda": hist.ebitda,
                "enterprise_value": ev_from_ebitda,
                "equity_value": equity_from_ebitda,
                "price_per_share": price_from_ebitda,
            },
            "per": {
                "multiple": per,
                "net_income": hist.net_income,
                "equity_value": equity_from_per,
                "price_per_share": price_from_per,
            },
            "market": {
                "market_cap": self.market_cap,
                "market_ev": self.market_ev,
                "current_price": hist.current_stock_price,
            }
        }
    
    # ========== 感応度分析 ==========
    
    def sensitivity_analysis(
        self,
        method: Literal["perpetuity", "exit_multiple"] = "perpetuity",
        wacc_range: Optional[List[float]] = None,
        param_range: Optional[List[float]] = None
    ) -> pd.DataFrame:
        """
        感応度分析（理論株価）
        
        Parameters
        ----------
        method : str
            "perpetuity" or "exit_multiple"
        wacc_range : list
            WACCの変動幅（例: [-0.01, -0.005, 0, 0.005, 0.01]）
        param_range : list
            永久成長率 or Exit Multipleの変動幅
        
        Returns
        -------
        pd.DataFrame
            感応度分析マトリクス
        """
        if wacc_range is None:
            wacc_range = [-0.01, -0.005, 0, 0.005, 0.01]
        
        if param_range is None:
            if method == "perpetuity":
                param_range = [-0.005, -0.0025, 0, 0.0025, 0.005]
            else:
                param_range = [-1.5, -0.75, 0, 0.75, 1.5]
        
        base_wacc = self.wacc
        base_param = (
            self.assumptions.terminal_growth_rate
            if method == "perpetuity"
            else self.assumptions.exit_ebitda_multiple
        )
        
        results = []
        for p_delta in param_range:
            row = []
            param = base_param + p_delta
            
            for w_delta in wacc_range:
                wacc = base_wacc + w_delta
                
                # FCF現在価値を再計算
                pv_fcf_sum = sum(
                    p.fcf / ((1 + wacc) ** p.discount_period)
                    for p in self.projections
                )
                
                # ターミナルバリュー
                if method == "perpetuity":
                    if wacc <= param:
                        price = np.nan
                    else:
                        tv = self.terminal_fcf * (1 + param) / (wacc - param)
                        pv_tv = tv * (1 / ((1 + wacc) ** self.projections[-1].discount_period))
                        ev = pv_fcf_sum + pv_tv
                        equity = ev - self.net_debt - self.historical.minority_interest
                        price = equity / self.historical.shares_outstanding
                else:
                    tv = self.terminal_ebitda * param
                    pv_tv = tv * (1 / ((1 + wacc) ** self.projections[-1].discount_period))
                    ev = pv_fcf_sum + pv_tv
                    equity = ev - self.net_debt - self.historical.minority_interest
                    price = equity / self.historical.shares_outstanding
                
                row.append(price)
            
            results.append(row)
        
        # DataFrame作成
        wacc_labels = [f"{(base_wacc + w) * 100:.1f}%" for w in wacc_range]
        if method == "perpetuity":
            param_labels = [f"{(base_param + p) * 100:.2f}%" for p in param_range]
        else:
            param_labels = [f"{base_param + p:.1f}x" for p in param_range]
        
        df = pd.DataFrame(results, index=param_labels, columns=wacc_labels)
        df.index.name = "永久成長率" if method == "perpetuity" else "Exit Multiple"
        df.columns.name = "WACC"
        
        return df
    
    # ========== レポート出力 ==========
    
    def summary(self) -> Dict:
        """サマリー情報"""
        return {
            "scenario": self.assumptions.scenario.value,
            "wacc": {
                "risk_free_rate": self.assumptions.risk_free_rate,
                "unlevered_beta": self.assumptions.unlevered_beta,
                "levered_beta": self.levered_beta,
                "de_ratio": self.assumptions.target_de_ratio,
                "erp": self.assumptions.equity_risk_premium,
                "size_premium": self.assumptions.size_premium,
                "cost_of_equity": self.cost_of_equity,
                "cost_of_debt_after_tax": self.after_tax_cost_of_debt,
                "wacc": self.wacc,
            },
            "valuation": {
                "perpetuity": {
                    "sum_pv_fcf": self.sum_pv_fcf,
                    "terminal_value": self.terminal_value_perpetuity(),
                    "pv_terminal_value": self.pv_terminal_value("perpetuity"),
                    "enterprise_value": self.enterprise_value("perpetuity"),
                    "net_debt": self.net_debt,
                    "equity_value": self.equity_value("perpetuity"),
                    "price_per_share": self.price_per_share("perpetuity"),
                    "upside": self.upside("perpetuity"),
                    "implied_exit_multiple": self.implied_exit_multiple(),
                    "tv_percentage": self.tv_percentage_perpetuity,
                },
                "exit_multiple": {
                    "sum_pv_fcf": self.sum_pv_fcf,
                    "terminal_value": self.terminal_value_exit_multiple(),
                    "pv_terminal_value": self.pv_terminal_value("exit_multiple"),
                    "enterprise_value": self.enterprise_value("exit_multiple"),
                    "net_debt": self.net_debt,
                    "equity_value": self.equity_value("exit_multiple"),
                    "price_per_share": self.price_per_share("exit_multiple"),
                    "upside": self.upside("exit_multiple"),
                    "implied_growth_rate": self.implied_perpetual_growth(),
                    "tv_percentage": self.tv_percentage_exit_multiple,
                }
            }
        }
    
    def projection_table(self) -> pd.DataFrame:
        """予測テーブル"""
        data = []
        for p in self.projections:
            data.append({
                "年度": p.label,
                "売上収益": p.revenue,
                "EBITDA": p.ebitda,
                "減価償却": p.depreciation,
                "EBIT": p.ebit,
                "NOPAT": p.ebit * (1 - self.assumptions.effective_tax_rate),
                "設備投資": -p.capex,
                "Δ運転資本": -p.delta_nwc,
                "FCF": p.fcf,
                "割引係数": p.discount_factor,
                "FCF現在価値": p.pv_fcf,
            })
        
        df = pd.DataFrame(data).set_index("年度").T
        return df


def update_assumptions(model: DCFModel, **kwargs) -> DCFModel:
    """
    前提条件を更新して新しいモデルを返す
    
    Usage
    -----
    new_model = update_assumptions(
        model,
        scenario=Scenario.BULL,
        terminal_growth_rate=0.025
    )
    """
    import copy
    new_assumptions = copy.deepcopy(model.assumptions)
    
    for key, value in kwargs.items():
        if hasattr(new_assumptions, key):
            setattr(new_assumptions, key, value)
    
    return DCFModel(assumptions=new_assumptions, historical=model.historical)


# ========== 使用例 ==========

if __name__ == "__main__":
    # モデル作成
    model = DCFModel()
    
    # サマリー表示
    summary = model.summary()
    
    print("=" * 60)
    print("DCF Valuation Summary - A株式会社")
    print("=" * 60)
    print(f"\nシナリオ: {summary['scenario']}")
    print(f"売上成長率: {model.assumptions.current_revenue_growth:.1%}")
    
    print(f"\n【WACC】")
    print(f"  リスクフリーレート: {summary['wacc']['risk_free_rate']:.2%}")
    print(f"  アンレバードβ: {summary['wacc']['unlevered_beta']:.2f}")
    print(f"  レバードβ: {summary['wacc']['levered_beta']:.2f}")
    print(f"  株主資本コスト: {summary['wacc']['cost_of_equity']:.2%}")
    print(f"  WACC: {summary['wacc']['wacc']:.2%}")
    
    print(f"\n【バリュエーション - 永久成長率法】")
    v = summary['valuation']['perpetuity']
    print(f"  FCF現在価値合計: ¥{v['sum_pv_fcf']:,.0f}百万円")
    print(f"  TV現在価値: ¥{v['pv_terminal_value']:,.0f}百万円")
    print(f"  企業価値(EV): ¥{v['enterprise_value']:,.0f}百万円")
    print(f"  株式価値: ¥{v['equity_value']:,.0f}百万円")
    print(f"  理論株価: ¥{v['price_per_share']:,.0f}")
    print(f"  アップサイド: {v['upside']:+.1%}")
    print(f"  インプライドEV/EBITDA: {v['implied_exit_multiple']:.1f}x")
    print(f"  TV/EV: {v['tv_percentage']:.1%}")
    
    print(f"\n【バリュエーション - Exit Multiple法】")
    v = summary['valuation']['exit_multiple']
    print(f"  企業価値(EV): ¥{v['enterprise_value']:,.0f}百万円")
    print(f"  株式価値: ¥{v['equity_value']:,.0f}百万円")
    print(f"  理論株価: ¥{v['price_per_share']:,.0f}")
    print(f"  アップサイド: {v['upside']:+.1%}")
    print(f"  インプライド永久成長率: {v['implied_growth_rate']:.2%}")
    
    print("\n【FCF予測】")
    print(model.projection_table().to_string())
    
    print("\n【感応度分析 - 永久成長率法】")
    print(model.sensitivity_analysis("perpetuity").to_string())
