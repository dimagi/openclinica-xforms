package org.openclinica.uconn;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Hashtable;
import java.util.List;

import org.apache.http.HttpResponse;
import org.apache.http.HttpStatus;
import org.apache.http.StatusLine;
import org.apache.http.auth.AuthScope;
import org.apache.http.auth.UsernamePasswordCredentials;
import org.apache.http.client.CredentialsProvider;
import org.apache.http.client.HttpClient;
import org.apache.http.client.methods.HttpGet;
import org.apache.http.client.params.AuthPolicy;
import org.apache.http.client.params.HttpClientParams;
import org.apache.http.client.protocol.ClientContext;
import org.apache.http.impl.client.BasicCredentialsProvider;
import org.apache.http.impl.client.DefaultHttpClient;
import org.apache.http.params.BasicHttpParams;
import org.apache.http.params.HttpParams;
import org.apache.http.protocol.BasicHttpContext;
import org.apache.http.protocol.HttpContext;
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
		final String STUDY_ID = "CPCS";
		String wsUrl = serverURL() + "/screening-report?subject_id=" + patientID + "&study_id=" + STUDY_ID;
		
        HttpResponse response = httpQuery(wsUrl);
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
	
	private static HttpResponse httpQuery(String url) throws IOException {
        HttpParams params = new BasicHttpParams();
        HttpClientParams.setAuthenticating(params, true);
        HttpClient httpclient = new DefaultHttpClient(params);

		HttpContext httpcontext = new BasicHttpContext();
		CredentialsProvider credsProvider = new BasicCredentialsProvider();
        httpcontext.setAttribute(ClientContext.CREDS_PROVIDER, credsProvider);
        credsProvider.setCredentials(AuthScope.ANY, new UsernamePasswordCredentials(username(), password()));

        return httpclient.execute(new HttpGet(url), httpcontext);
	}
	
	private static String serverURL() {
//		SharedPreferences sp = PreferenceManager.getDefaultSharedPreferences(Collect.getInstance().getApplicationContext());
//		return sp.getString(PreferencesActivity.KEY_SERVER_URL, null);
		
		//TODO make this a setting
		return "http://mrgris.com:8053";
		//return "https://mrgris.com:8053";
	}
	
	private static String username() {
		return "droos";
	}
	
	private static String password() {
		return "password";
	}
	
}
