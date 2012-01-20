package org.openclinica.uconn;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.Hashtable;

import org.apache.http.HttpResponse;
import org.apache.http.HttpStatus;
import org.apache.http.StatusLine;
import org.apache.http.client.HttpClient;
import org.apache.http.client.methods.HttpGet;
import org.apache.http.impl.client.DefaultHttpClient;
import org.json.JSONException;
import org.json.JSONObject;

public class PatientLookup {

	public static final boolean DEBUG = false;
	
	//is the cache necessary now that we're not in a function handler?
	static Hashtable<String, String> cache = new Hashtable<String, String>();

	public static String screeningReportURL(String patientID) {
//		Boolean result = cache.get(pat_id);
//		if (result == null) {
			try {
				return screeningLookupWebService(patientID);
			} catch (IOException ioe) {
				//TODO how should we handle this for real?
				throw new RuntimeException("could not contact web service");
			}
//			cache.put(pat_id, result);
//		}
//		return result.booleanValue();
	}

	protected static String screeningLookupWebService(String patientID) throws IOException {
		if (DEBUG) {
			return needsScreeningWebServiceStub(patientID);
		}
		
		final String STUDY_ID = "CPCS";
		String wsUrl = serverURL() + "/screening-report?subject_id=" + patientID + "&study_id=" + STUDY_ID;
		
		HttpClient httpclient = new DefaultHttpClient();
	    HttpResponse response = httpclient.execute(new HttpGet(wsUrl));
	    StatusLine statusLine = response.getStatusLine();
	    if(statusLine.getStatusCode() == HttpStatus.SC_OK){
	        ByteArrayOutputStream out = new ByteArrayOutputStream();
	        response.getEntity().writeTo(out);
	        out.close();
	        String responseString = out.toString();
	        
			try {
		        JSONObject resp = new JSONObject(responseString);
		        return (resp.isNull("url") ? null : resp.getString("url"));
			} catch (JSONException e) {
				throw new RuntimeException(e);
			}
	        
	        //TODO close conn in a finally?
	    } else{

	    	response.getEntity().getContent().close();
	        throw new IOException(statusLine.getReasonPhrase());
	    }
	}
	
	private static String needsScreeningWebServiceStub(String patientID) {
		return (patientID.charAt(patientID.length() - 1) % 2 == 0 ? "http://google.com" : "");
	}

	private static String serverURL() {
//		SharedPreferences sp = PreferenceManager.getDefaultSharedPreferences(Collect.getInstance().getApplicationContext());
//		return sp.getString(PreferencesActivity.KEY_SERVER_URL, null);
		
		return "http://mrgris.com:8053"; //TODO make this a setting
	}

}
