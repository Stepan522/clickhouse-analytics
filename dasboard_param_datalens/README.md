# Ссылка на дашборд

https://datalens.yandex/ixyoh7x60mus2

## Задача

Продемонстрировать возможность DataLens с использованием сложной визуализации - создание дефолтный чартов с использованием параметров.

### Особенности

С помощью parameters были созданы два селектор:
1) Период (scaleru): Год, квартал, месяц, неделя, день
2) Числовые показатели (metric): визиты, лиды, доходы и др.

## Формулы

### Дата параметром:

-IF [scaleru]="Год" THEN DATETRUNC([date],"year")
-ELSEIF [scaleru]="Квартал" THEN DATETRUNC([date],"quarter")
-ELSEIF [scaleru]="Месяц" THEN DATETRUNC([date],"month")
-ELSEIF [scaleru]="Неделя" THEN DATETRUNC([date],"week")
-ELSEIF [scaleru]="День" THEN DATETRUNC([date],"day")
-END

### Показатель:

if([metric]='Визиты', SUM([visits]),
[metric]='Динамика визитов, %', [Динамика визитов],
[metric]='Кол-во заказов', SUM([purchases]),
[metric]='Сумма заказов, руб', SUM([revenue]),
[metric]='Кол-во заказанных шт товара', SUM([aty_sku_zakaza]),
[metric]='Выкупаемость', [Выкупаемость],
[metric]='Установки', sum([installs]),
null)

### Скрин настроек чарта

<img width="1308" height="678" alt="image" src="https://github.com/user-attachments/assets/eec12262-4be6-43df-8997-bad319d9d09f" />


## Результат

В результате можно создавать динамические чарты сравнения выбранного показателя за выбранный период, как в таблицах, так и в графиках.


