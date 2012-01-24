package org.openclinica.uconn;

import java.io.File;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.xpath.XPath;
import javax.xml.xpath.XPathConstants;
import javax.xml.xpath.XPathExpressionException;
import javax.xml.xpath.XPathFactory;

import org.w3c.dom.Document;

import android.app.Activity;
import android.content.ContentUris;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.BaseColumns;
import android.util.Log;
import android.view.View;
import android.widget.Toast;

public class Main extends Activity {
    /** Called when the activity is first created. */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.main);
    }

    public static final int REQ_SCREENING_ID_ENTRY = 1;
    public static final int REQ_SCREENING_PAT_REG = 2;
    public static final int REQ_SCREENING_MAIN = 3;
    public static final int REQ_SCREENING_SUBMIT = 4;
    public static final int REQ_SCREENING_LOOKUP = 5;
    
	public static final String PATID_FORM_ID = "http://dimagi.com/uconn-screening/patient-id";
	public static final String REG_FORM_ID = "http://dimagi.com/uconn-screening/patient-reg";
	public static final String SCREENING_FORM_ID = "http://openclinica.org/xform/S_CPCS/v1.0.0/SE_CPCS/";

    public void startScreening(View v) {
    	launchFormEntry(PATID_FORM_ID, REQ_SCREENING_ID_ENTRY, null, null);
    }
    
    public void loadScreening(View v) {
    	launchFormEntry(PATID_FORM_ID, REQ_SCREENING_LOOKUP, null, null);
    }

    public void startScreeningReg(Uri instanceUri) {
    	InstanceData inst = getFormInstance(instanceUri);
    	Bundle context = new Bundle();
    	context.putString("pat-id", inst.get("/pat_id/pat_id"));
    	launchFormEntry(REG_FORM_ID, REQ_SCREENING_PAT_REG, context, null);
    }
    
    public void startScreeningPatient(Uri instanceUri) {
    	InstanceData inst = getFormInstance(instanceUri);
    	String patientID = inst.get("/reg/pat_id");
    	String initials = inst.get("/reg/initials");
    	String lang = inst.get("/reg/lang");
    	boolean lowliteracy = "y".equals(inst.get("/reg/low_literacy"));

    	Bundle context = new Bundle();
    	context.putString("pat-id", patientID);
    	context.putString("initials", initials);
    	Bundle config = new Bundle();
    	config.putString("lang", lang);
    	//config.putBoolean("lowlit", lowliteracy);
    	launchFormEntry(SCREENING_FORM_ID, REQ_SCREENING_MAIN, context, config);
    }
    
    public String lookupPatient(Uri uri) {
    	InstanceData inst = getFormInstance(uri);
    	String patientID = inst.get("/pat_id/pat_id");

		Toast toast = Toast.makeText(this, "Please wait while we look up this patient.", Toast.LENGTH_SHORT);
		toast.show();
    	
    	return PatientLookup.screeningReportURL(patientID);
    }
    
    public Uri formByNamespace(String xmlns) {
    	String AUTHORITY = "org.odk.collect.android.provider.odk.forms";
    	Uri FORMS_BASE_URI = Uri.parse("content://" + AUTHORITY + "/forms");
    	String FORM_ID_COL = "jrFormId";
    	
    	long formID = -1;
    	Cursor c = managedQuery(FORMS_BASE_URI, null, FORM_ID_COL + " = '" + xmlns + "'", null, null);
   	    if (c.moveToFirst()) {
   		    do {
   		    	formID = c.getLong(c.getColumnIndex(BaseColumns._ID));
   		    } while (c.moveToNext());
   	    }
   	    if (formID == -1) {
   	    	throw new RuntimeException("can't find screening form! [" + xmlns + "]");
   	    }
   	    
   	    return ContentUris.withAppendedId(FORMS_BASE_URI, formID);
    }
    
    protected void launchFormEntry(String xmlns, int requestCode, Bundle context, Bundle config) {
    	Intent i = new Intent(Intent.ACTION_EDIT, formByNamespace(xmlns));
    	if (config != null) {
    		i.putExtras(config);
    	}
    	i.putExtra("contextvars", context);
    	startActivityForResult(i, requestCode);
    }
    
    protected void launchViewReport(String reportURL) {
		Intent i = new Intent(this, ResultsActivity.class);
		i.putExtra("url", reportURL);
		startActivity(i);
    }
    
    public interface InstanceData {
    	String get(String xpath);
    }
    
    protected InstanceData getFormInstance(Uri uri) {
    	try {
	    	String instancePath = null;    	
	    	Cursor c = managedQuery(uri, null, null, null, null);
	   	    if (c.moveToFirst()) {
	   		    do {
	   		    	instancePath = c.getString(c.getColumnIndex("instanceFilePath"));
	   		    } while (c.moveToNext());
	   	    }
	    	
	   	    DocumentBuilderFactory builderFactory = DocumentBuilderFactory.newInstance();
	   	    builderFactory.setNamespaceAware(false);
	   	    DocumentBuilder builder = builderFactory.newDocumentBuilder();
	   	    final Document document = builder.parse(new File(instancePath));
	   	    
	   	    final XPath xp = XPathFactory.newInstance().newXPath();
	   	    return new InstanceData() {
				public String get(String xpath) {
			   	    try {
						return (String)xp.evaluate(xpath, document, XPathConstants.STRING);
					} catch (XPathExpressionException e) {
						throw new RuntimeException(e);
					}
				}
	   	    };
    	} catch (Exception e) {
    		throw new RuntimeException(e);
    	}
    }
    
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
    	if (resultCode != RESULT_OK) {
    		return;
    	}
    	
    	if (requestCode == REQ_SCREENING_ID_ENTRY) {
    		String screeningReport = lookupPatient(data.getData());    		
    		if (screeningReport == null) {
				startScreeningReg(data.getData());
			} else {
				Toast toast = Toast.makeText(this, "This patient already has a completed screening form on file.", Toast.LENGTH_SHORT);
				toast.show();
			}    		
    	} else if (requestCode == REQ_SCREENING_LOOKUP) {
    		String screeningReport = lookupPatient(data.getData());    		
			if (screeningReport == null) {
				Toast toast = Toast.makeText(this, "There is no screening form on file for this patient ID.", Toast.LENGTH_SHORT);
				toast.show();
			} else {
				launchViewReport(screeningReport);
			}
    	} else if (requestCode == REQ_SCREENING_PAT_REG) {
    		startScreeningPatient(data.getData());

    	
    	
    	} else if (requestCode == REQ_SCREENING_MAIN) {
    		Uri instanceUri = data.getData();
	   	    startActivityForResult(new Intent(Intent.ACTION_SYNC, instanceUri), REQ_SCREENING_SUBMIT);
    	} else if (requestCode == REQ_SCREENING_SUBMIT) {
    		if (resultCode == RESULT_OK) {
    			String resp = data.getExtras().getString("response");

    			Intent i = new Intent(this, ResultsActivity.class);
    			i.putExtra("url", resp);
    			startActivity(i);
    		}
    	}
    }
        
}
