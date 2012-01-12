package org.openclinica.uconn;

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

    public static final int REQUEST_FORM_ENTRY = 1;
    public static final int REQUEST_FORM_SUBMIT = 2;
    
    public void startScreening(View v) {
    	//invoke ODK
    	
    	String AUTHORITY = "org.odk.collect.android.provider.odk.forms";
    	Uri FORMS_BASE_URI = Uri.parse("content://" + AUTHORITY + "/forms");
    	String FORM_ID_COL = "jrFormId";
    	String SCREENING_FORM_ID = "http://openclinica.org/xform/S_CPCS/v1.0.0/SE_CPCS/";
    	
    	long formID = -1;
    	Cursor c = managedQuery(FORMS_BASE_URI, null, FORM_ID_COL + " = '" + SCREENING_FORM_ID + "'", null, null);
   	    if (c.moveToFirst()) {
   		    do {
   		    	formID = c.getLong(c.getColumnIndex(BaseColumns._ID));
   		    } while (c.moveToNext());
   	    }
   	    if (formID == -1) {
   	    	throw new RuntimeException("can't find screening form! [" + SCREENING_FORM_ID + "]");
   	    }
   	    
   	    Uri formUri = ContentUris.withAppendedId(FORMS_BASE_URI, formID);
   	    startActivityForResult(new Intent(Intent.ACTION_EDIT, formUri), REQUEST_FORM_ENTRY);
    }
    
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
    	if (requestCode == REQUEST_FORM_ENTRY) {
    		if (resultCode == RESULT_OK) {
    			Uri instanceUri = data.getData();
    	   	    startActivityForResult(new Intent(Intent.ACTION_SYNC, instanceUri), REQUEST_FORM_SUBMIT);
    		}
    	} else if (requestCode == REQUEST_FORM_SUBMIT) {
    		if (resultCode == RESULT_OK) {
    			String resp = data.getExtras().getString("response");
    			
    			Intent i = new Intent(this, ResultsActivity.class);
    			i.putExtra("url", resp);
    			startActivity(i);
    		}
    	}
    }
        
}
