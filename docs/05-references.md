# 참고 자료

이 자료는 초기 기획 단계에서 2026-06-20에 확인했고, 데이터 공급원 우선순위는 2026-06-21에 다시 점검했다.

## 증권사와 시장 데이터

- 한국투자증권 Open API 포털: https://apiportal.koreainvestment.com/
- 한국투자증권 샘플 저장소: https://github.com/koreainvestment/open-trading-api
- KIS API 가이드 페이지: https://apiportal.koreainvestment.com/apiservice-apiservice
- KRX 정보데이터시스템: https://data.krx.co.kr/
- KRX Open API: https://openapi.krx.co.kr/
- KRX Open API 이용방법: https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO003.jsp
- KRX Open API 서비스 목록: https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd
- Yahoo Finance 약관: https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.html
- OpenDART: https://opendart.fss.or.kr/
- FinanceDataReader: https://github.com/FinanceData/FinanceDataReader
- pykrx: https://github.com/sharebook-kr/pykrx
- pykrx PyPI: https://pypi.org/project/pykrx/
- yfinance: https://github.com/ranaroussi/yfinance
- yfinance 문서: https://ranaroussi.github.io/yfinance/

2026-06-21 기준 데이터 공급원 결정:

- KIS Open API는 현재가, 기간별 시세, 분봉, 재무비율, 수급/공매도/신용잔고/프로그램 매매, 순위분석, 실시간 시세, 계좌/주문을 제공하므로 초기 실제 데이터와 향후 자동매매 연결의 중심으로 둔다.
- KRX Open API는 2010년 이후 주식 일별매매정보와 종목기본정보 등을 제공하므로 승인 후 백테스트용 공식 장기 데이터 공급원으로 둔다.
- KRX 승인이 지연되면 Yahoo/yfinance를 백테스트 개발용 임시 과거 가격 데이터로 사용한다. Yahoo/yfinance는 약관과 안정성 제약이 있으므로 정식 한국 주식 데이터 공급원으로 고정하지 않는다.
- `pykrx`, FinanceDataReader는 검증 또는 임시 보조 후보로 유지한다.

백테스트 비교군에 사용하는 Yahoo Finance 지수 티커:

- KOSPI 200: `^KS200`
- KOSDAQ 대표지수: `^KQ11`
- S&P 500: `^GSPC`
- Nasdaq 100: `^NDX`

## 플랫폼

- MySQL LTS와 Innovation 릴리스 모델: https://dev.mysql.com/doc/refman/8.4/en/mysql-releases.html
- Spring Boot 프로젝트 페이지: https://spring.io/projects/spring-boot/
- Spring Boot 시스템 요구사항: https://docs.spring.io/spring-boot/system-requirements.html
- SvelteKit 소개: https://svelte.dev/docs/kit/introduction
- Node.js 릴리스 일정: https://nodejs.org/en/about/previous-releases
- Python 버전 상태: https://devguide.python.org/versions/
- Oracle Java SE 지원 로드맵: https://www.oracle.com/java/technologies/java-se-support-roadmap.html
- Docker Desktop Mac 설치 가이드: https://docs.docker.com/desktop/setup/install/mac-install/
- MySQL Docker 공식 이미지: https://hub.docker.com/_/mysql

## UI 참고 후보

나중에 UI 방향을 검토할 때 볼 후보이며, 아직 결정 사항은 아니다.

- TradingView: https://www.tradingview.com/
- Finviz: https://finviz.com/
- Koyfin: https://www.koyfin.com/
- QuantConnect: https://www.quantconnect.com/
- Portfolio Visualizer: https://www.portfoliovisualizer.com/
- Naver Finance: https://finance.naver.com/

## 전략 참고 자료

- Jegadeesh/Titman 모멘텀 논문: https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1993.tb04702.x
- Fama/French 팩터 논문: https://www.bauer.uh.edu/rsusmel/phd/Fama-French_JFE93.pdf
- Piotroski F-Score 논문 정보: https://www.gsb.stanford.edu/faculty-research/publications/value-investing-use-historical-financial-statement-information
- IBD CAN SLIM 소개: https://www.investors.com/ibd-videos/homestudy/1-introduction-to-can-slim/
- Donchian Channel 설명: https://www.investopedia.com/donchian-channels-formula-8415235
