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

public class Main extends Activity {
    /** Called when the activity is first created. */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.main);
    }

    public static final int REQ_SCREENING_REG = 1;
    public static final int REQ_SCREENING_ENTRY = 2;
    public static final int REQ_SCREENING_SUBMIT = 3;
    public static final int REQ_SCREENING_LOOKUP = 4;
    
	public static final String REG_FORM_ID = "http://dimagi.com/uconn-screening/patient-reg";
	public static final String SCREENING_FORM_ID = "http://openclinica.org/xform/S_CPCS/v1.0.0/SE_CPCS/";

    public void startScreening(View v) {
    	Bundle context = new Bundle();
    	context.putBoolean("lookup-only", false);
    	launchFormEntry(REG_FORM_ID, REQ_SCREENING_REG, context);
    }
    
    public void startScreeningPatient(Uri instanceUri) {
    	InstanceData inst = getFormInstance(instanceUri);
    	Log.i("plsplspls", inst.get("/reg/pat_id"));
    	Log.i("plsplspls", inst.get("/reg/demog/initials"));
    }
    
    public void loadScreening(View v) {
    	Bundle context = new Bundle();
    	context.putBoolean("lookup-only", true);
    	launchFormEntry(REG_FORM_ID, REQ_SCREENING_LOOKUP, context);
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
    
    protected void launchFormEntry(String xmlns, int requestCode, Bundle context) {
    	Intent i = new Intent(Intent.ACTION_EDIT, formByNamespace(xmlns));
    	i.putExtra("contextvars", context);
    	startActivityForResult(i, requestCode);
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
    	
    	if (requestCode == REQ_SCREENING_REG) {
    		startScreeningPatient(data.getData());
    	} else if (requestCode == REQ_SCREENING_ENTRY) {
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
