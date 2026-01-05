import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import matplotlib.pyplot as plt

# تهيئة صفحة Streamlit
st.set_page_config(page_title="تحليل سجل الأحداث", layout="wide")
st.title("📊 تحليل سجل الأحداث الصناعية (Logbook Analysis)")
st.markdown("### حساب MTTR, MTBF وتكرارات الأحداث")

# رفع الملف
uploaded_file = st.file_uploader("اختر ملف السجل (Logbook_YYYYMMDD.txt)", type="txt")

if uploaded_file is not None:
    # قراءة الملف
    lines = uploaded_file.readlines()
    
    # تحويل bytes إلى نص إذا لزم الأمر
    if isinstance(lines[0], bytes):
        lines = [line.decode('utf-8') for line in lines]
    else:
        lines = [line for line in lines]
    
    # معالجة البيانات
    data = []
    for line in lines:
        # تخطي الأسطر الفارغة أو رؤوس الجداول
        if line.startswith("=") or line.strip() == "":
            continue
        
        parts = line.split("\t")
        
        # التأكد من وجود 4 أعمدة
        while len(parts) < 4:
            parts.append("")
        
        # تنظيف البيانات
        cleaned_parts = [part.strip() for part in parts]
        
        # التأكد من وجود تاريخ ووقت
        if len(cleaned_parts) >= 2 and cleaned_parts[0] and cleaned_parts[1]:
            data.append(cleaned_parts[:4])  # أخذ أول 4 أعمدة فقط
    
    # إنشاء DataFrame
    df = pd.DataFrame(data, columns=["Date", "Time", "Event", "Details"])
    
    # عرض البيانات الأصلية
    st.subheader("📄 البيانات الأصلية")
    st.dataframe(df.head(100), use_container_width=True)
    
    # تحويل التاريخ والوقت إلى كائن datetime
    df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='%d.%m.%Y %H:%M:%S', errors='coerce')
    
    # إزالة الصفوف التي لا تحتوي على تاريخ/وقت صحيح
    df = df.dropna(subset=['DateTime']).sort_values('DateTime').reset_index(drop=True)
    
    # إنشاء علامات للأحداث (محطات توقف/إخفاقات)
    # تحديد الأحداث التي تمثل إخفاقات/مشاكل (بالاعتماد على الأكواد التي تبدأ بـ E أو W)
    failure_patterns = ['E', 'W', 'T']  # رموز الأخطاء والتحذيرات
    df['IsFailure'] = df['Event'].apply(lambda x: any(x.startswith(pattern) for pattern in failure_patterns))
    df['IsStoppage'] = df['Event'].str.contains('stopped|Stopped|machine stopped', case=False, na=False)
    
    # تحديد أحداث بدء التشغيل
    df['IsStartup'] = df['Event'].str.contains('Starting speed|Automatic mode|starting', case=False, na=False)
    
    # ==================== قسم 1: حساب تكرارات الأحداث ====================
    st.subheader("📈 1. تحليل تكرارات الأحداث")
    
    # حساب تكرارات الأحداث
    event_counts = df['Event'].value_counts().reset_index()
    event_counts.columns = ['Event', 'Count']
    
    # عرض أهم 20 حدثًا
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**أكثر 20 حدث تكرارًا:**")
        st.dataframe(event_counts.head(20), use_container_width=True)
    
    with col2:
        # رسم بياني لتكرارات الأحداث
        fig1 = px.bar(event_counts.head(20), 
                     x='Count', 
                     y='Event',
                     orientation='h',
                     title='أكثر 20 حدث تكرارًا',
                     color='Count',
                     color_continuous_scale='viridis')
        fig1.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig1, use_container_width=True)
    
    # تحليل الأحداث حسب التصنيف
    failure_events = df[df['IsFailure']]['Event'].value_counts()
    if not failure_events.empty:
        st.markdown("**توزيع أحداث الإخفاق (بالرمز):**")
        failure_df = failure_events.reset_index()
        failure_df.columns = ['Event Code', 'Count']
        
        fig2 = px.pie(failure_df.head(10), 
                     values='Count', 
                     names='Event Code',
                     title='توزيع رموز الأخطاء (أعلى 10)')
        st.plotly_chart(fig2, use_container_width=True)
    
    # ==================== قسم 2: حساب MTBF (Mean Time Between Failures) ====================
    st.subheader("⏱️ 2. حساب MTBF (متوسط الوقت بين الأعطال)")
    
    # تحديد أوقات بداية ونهاية التشغيل
    operation_periods = []
    current_start = None
    current_end = None
    
    for i in range(len(df)):
        if df.iloc[i]['IsStartup'] and current_start is None:
            current_start = df.iloc[i]['DateTime']
        elif (df.iloc[i]['IsFailure'] or df.iloc[i]['IsStoppage']) and current_start is not None:
            current_end = df.iloc[i]['DateTime']
            if current_start and current_end:
                operation_periods.append((current_start, current_end))
                current_start = None
                current_end = None
    
    # حساب MTBF
    if operation_periods and len(operation_periods) > 1:
        time_between_failures = []
        for i in range(1, len(operation_periods)):
            # الوقت بين نهاية فترة التشغيل السابقة وبداية التالية
            time_diff = (operation_periods[i][0] - operation_periods[i-1][1]).total_seconds() / 60  # بالدقائق
            if time_diff > 0:  # تجاهل الفروق السلبية
                time_between_failures.append(time_diff)
        
        if time_between_failures:
            mttf = np.mean(time_between_failures)
            mttf_std = np.std(time_between_failures)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("MTBF (متوسط الوقت بين الأعطال)", f"{mttf:.2f} دقيقة")
            with col2:
                st.metric("الانحراف المعياري", f"{mttf_std:.2f} دقيقة")
            with col3:
                st.metric("عدد فترات التشغيل", len(time_between_failures))
            
            # رسم توزيع الأوقات بين الأعطال
            fig3 = go.Figure()
            fig3.add_trace(go.Histogram(x=time_between_failures, 
                                       nbinsx=20,
                                       name='فترات التشغيل',
                                       marker_color='green'))
            fig3.add_vline(x=mttf, line_dash="dash", line_color="red", 
                          annotation_text=f"MTBF: {mttf:.1f} دقيقة")
            fig3.update_layout(title='توزيع الأوقات بين الأعطال',
                              xaxis_title='الوقت (دقيقة)',
                              yaxis_title='التكرار')
            st.plotly_chart(fig3, use_container_width=True)
    
    # ==================== قسم 3: حساب MTTR (Mean Time To Repair) ====================
    st.subheader("🔧 3. حساب MTTR (متوسط وقت الإصلاح)")
    
    # تحديد فترات التوقف (من وقت حدوث العطل إلى وقت إعادة التشغيل)
    repair_times = []
    
    for i in range(len(df) - 1):
        if df.iloc[i]['IsFailure'] or df.iloc[i]['IsStoppage']:
            failure_time = df.iloc[i]['DateTime']
            
            # البحث عن أقرب حدث بدء تشغيل بعد العطل
            for j in range(i + 1, len(df)):
                if df.iloc[j]['IsStartup']:
                    repair_time = df.iloc[j]['DateTime']
                    repair_duration = (repair_time - failure_time).total_seconds() / 60  # بالدقائق
                    if 0 < repair_duration < 1440:  # تجاهل الفترات الأطول من يوم (ربما بيانات غير صحيحة)
                        repair_times.append({
                            'Failure': df.iloc[i]['Event'],
                            'FailureTime': failure_time,
                            'RepairTime': repair_time,
                            'Duration': repair_duration
                        })
                    break
    
    if repair_times:
        repair_df = pd.DataFrame(repair_times)
        mttr = repair_df['Duration'].mean()
        mttr_std = repair_df['Duration'].std()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("MTTR (متوسط وقت الإصلاح)", f"{mttr:.2f} دقيقة")
        with col2:
            st.metric("الانحراف المعياري", f"{mttr_std:.2f} دقيقة")
        with col3:
            st.metric("عدد حالات الإصلاح", len(repair_times))
        
        # عرض فترات الإصلاح
        st.markdown("**تفاصيل فترات الإصلاح:**")
        st.dataframe(repair_df, use_container_width=True)
        
        # رسم توزيع أوقات الإصلاح
        fig4 = go.Figure()
        fig4.add_trace(go.Histogram(x=repair_df['Duration'], 
                                   nbinsx=20,
                                   name='أوقات الإصلاح',
                                   marker_color='red'))
        fig4.add_vline(x=mttr, line_dash="dash", line_color="blue", 
                      annotation_text=f"MTTR: {mttr:.1f} دقيقة")
        fig4.update_layout(title='توزيع أوقات الإصلاح',
                          xaxis_title='الوقت (دقيقة)',
                          yaxis_title='التكرار')
        st.plotly_chart(fig4, use_container_width=True)
        
        # تحليل أوقات الإصلاح حسب نوع العطل
        repair_by_failure = repair_df.groupby('Failure')['Duration'].agg(['mean', 'count', 'std']).reset_index()
        repair_by_failure = repair_by_failure.sort_values('count', ascending=False)
        
        st.markdown("**متوسط وقت الإصلاح حسب نوع العطل:**")
        fig5 = px.bar(repair_by_failure.head(10), 
                     x='mean', 
                     y='Failure',
                     orientation='h',
                     title='متوسط وقت الإصلاح حسب نوع العطل (أعلى 10)',
                     color='count',
                     color_continuous_scale='blues')
        fig5.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig5, use_container_width=True)
    
    # ==================== قسم 4: التحليل الزمني بين الأحداث ====================
    st.subheader("📅 4. التحليل الزمني بين الأحداث")
    
    # حساب الفترات الزمنية بين جميع الأحداث المتتالية
    df['TimeDiff'] = df['DateTime'].diff().dt.total_seconds() / 60  # الفرق بالدقائق
    
    # عرض الفترات الزمنية بين الأحداث
    st.markdown("**الفترات الزمنية بين الأحداث المتتالية:**")
    time_diff_df = df[['DateTime', 'Event', 'Details', 'TimeDiff']].copy()
    st.dataframe(time_diff_df.head(50), use_container_width=True)
    
    # إحصائيات الفترات الزمنية
    st.markdown("**إحصائيات الفترات الزمنية بين الأحداث:**")
    time_stats = time_diff_df['TimeDiff'].describe()
    st.write(time_stats)
    
    # رسم الفترات الزمنية على خط الزمن
    fig6 = go.Figure()
    fig6.add_trace(go.Scatter(x=df['DateTime'], 
                             y=df['TimeDiff'].fillna(0),
                             mode='markers+lines',
                             name='الفترة بين الأحداث',
                             marker=dict(size=6, color=df['TimeDiff'].fillna(0), 
                                        colorscale='viridis', showscale=True,
                                        colorbar=dict(title="دقائق")),
                             text=df['Event']))
    fig6.update_layout(title='الفترات الزمنية بين الأحداث على خط الزمن',
                      xaxis_title='الوقت',
                      yaxis_title='الفترة بين الأحداث (دقيقة)')
    st.plotly_chart(fig6, use_container_width=True)
    
    # ==================== قسم 5: التحليل المتقدم ====================
    st.subheader("📊 5. تحليل متقدم")
    
    # تحليل حسب نوبات العمل
    df['Hour'] = df['DateTime'].dt.hour
    df['Shift'] = pd.cut(df['Hour'], 
                        bins=[0, 8, 16, 24], 
                        labels=['الوردية الثالثة', 'الوردية الأولى', 'الوردية الثانية'])
    
    # حساب تكرار الأحداث حسب الوردية
    events_by_shift = df[df['IsFailure']].groupby('Shift')['Event'].count().reset_index()
    events_by_shift.columns = ['الوردية', 'عدد الأحداث']
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**توزيع الأحداث حسب الوردية:**")
        st.dataframe(events_by_shift, use_container_width=True)
        
        fig7 = px.pie(events_by_shift, 
                     values='عدد الأحداث', 
                     names='الوردية',
                     title='توزيع الأحداث حسب الوردية',
                     color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig7, use_container_width=True)
    
    with col2:
        # تحليل حسب اليوم والساعة
        df['Hour'] = df['DateTime'].dt.hour
        hourly_events = df[df['IsFailure']].groupby('Hour').size().reset_index()
        hourly_events.columns = ['الساعة', 'عدد الأحداث']
        
        fig8 = px.line(hourly_events, 
                      x='الساعة', 
                      y='عدد الأحداث',
                      title='توزيع الأحداث على مدار الساعة',
                      markers=True)
        fig8.update_xaxes(range=[0, 23])
        st.plotly_chart(fig8, use_container_width=True)
    
    # ==================== قسم 6: الملخص التنفيذي ====================
    st.subheader("📋 6. الملخص التنفيذي")
    
    # إنشاء بطاقات ملخصة
    total_events = len(df)
    failure_events_count = df['IsFailure'].sum()
    stoppage_events_count = df['IsStoppage'].sum()
    unique_events = df['Event'].nunique()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("إجمالي الأحداث", f"{total_events:,}")
    with col2:
        st.metric("أحداث إخفاق", f"{failure_events_count:,}")
    with col3:
        st.metric("أحداث توقف", f"{stoppage_events_count:,}")
    with col4:
        st.metric("أنواع أحداث مختلفة", f"{unique_events:,}")
    
    # حساب التوفر (Availability)
    if 'repair_times' in locals() and repair_times and 'time_between_failures' in locals() and time_between_failures:
        total_operation_time = sum(time_between_failures) + sum(repair_df['Duration'])
        if total_operation_time > 0:
            availability = (sum(time_between_failures) / total_operation_time) * 100
            st.metric("التوفر (%)", f"{availability:.2f}%")
    
    # الأحداث الأكثر تكرارًا مع نسبتها
    top_events = event_counts.head(10).copy()
    top_events['النسبة %'] = (top_events['Count'] / total_events * 100).round(2)
    
    st.markdown("**الأحداث العشرة الأكثر تكرارًا:**")
    st.dataframe(top_events, use_container_width=True)
    
    # زر لحفظ النتائج
    if st.button("💾 حفظ النتائج في ملف Excel"):
        # إنشاء كاتب Excel
        with pd.ExcelWriter('logbook_analysis_results.xlsx') as writer:
            df.to_excel(writer, sheet_name='البيانات الأصلية', index=False)
            
            if 'repair_df' in locals():
                repair_df.to_excel(writer, sheet_name='أوقات الإصلاح', index=False)
            
            event_counts.to_excel(writer, sheet_name='تكرارات الأحداث', index=False)
            
            # إنشاء ملخص
            summary_data = {
                'المؤشر': ['إجمالي الأحداث', 'أحداث إخفاق', 'أحداث توقف', 'أنواع أحداث مختلفة'],
                'القيمة': [total_events, failure_events_count, stoppage_events_count, unique_events]
            }
            
            if 'mttf' in locals():
                summary_data['المؤشر'].append('MTBF (دقيقة)')
                summary_data['القيمة'].append(round(mttf, 2))
            
            if 'mttr' in locals():
                summary_data['المؤشر'].append('MTTR (دقيقة)')
                summary_data['القيمة'].append(round(mttr, 2))
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='الملخص', index=False)
        
        st.success("تم حفظ النتائج في ملف 'logbook_analysis_results.xlsx'")
        
        # تقديم رابط للتنزيل
        with open('logbook_analysis_results.xlsx', 'rb') as f:
            excel_data = f.read()
        
        st.download_button(
            label="📥 تنزيل ملف Excel",
            data=excel_data,
            file_name="logbook_analysis_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.info("⬆️ يرجى رفع ملف السجل لبدء التحليل")

# تعليمات الاستخدام
with st.expander("📖 تعليمات الاستخدام"):
    st.markdown("""
    ### كيفية استخدام أداة تحليل السجل:
    
    1. **رفع الملف**: قم برفع ملف السجل النصي (Logbook_YYYYMMDD.txt)
    2. **تحليل البيانات**: سيقوم البرنامج تلقائيًا بـ:
       - حساب تكرارات كل حدث
       - حساب MTBF (متوسط الوقت بين الأعطال)
       - حساب MTTR (متوسط وقت الإصلاح)
       - تحليل الفترات الزمنية بين الأحداث
    3. **تصدير النتائج**: يمكنك حفظ النتائج في ملف Excel
    
    ### تعريف المؤشرات:
    - **MTBF (Mean Time Between Failures)**: متوسط الوقت بين الأعطال المتتالية
    - **MTTR (Mean Time To Repair)**: متوسط الوقت اللازم لإصلاح العطل
    - **التوفر**: نسبة الوقت الذي يكون فيه النظام قيد التشغيل
    
    ### ملاحظات:
    - يتم تحديد الأعطال تلقائيًا بناءً على رموز الأخطاء (E, W, T)
    - يتم حساب الأوقات بالدقائق
    - يمكن تحميل الملفات ذات الصيغة TXT فقط
    """)
