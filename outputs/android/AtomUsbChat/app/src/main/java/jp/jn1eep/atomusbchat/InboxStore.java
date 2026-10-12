package jp.jn1eep.atomusbchat;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.List;

/** Small durable history for USB inbox packets. Commit to disk before acknowledging ATOM. */
final class InboxStore {
    static final class Item {
        final String key, source, text;
        final boolean group;
        Item(String key,String source,String text,boolean group){this.key=key;this.source=source;this.text=text;this.group=group;}
    }
    enum Result { NEW, DUPLICATE, FAILED }
    private static final int HISTORY_LIMIT=64;
    private final SharedPreferences preferences;
    InboxStore(Context context){preferences=context.getApplicationContext().getSharedPreferences("usb_inbox",Context.MODE_PRIVATE);}
    synchronized Result save(String key,String source,String text,boolean group){
        try {
            JSONArray history=new JSONArray(preferences.getString("history","[]"));
            for(int i=0;i<history.length();++i)if(key.equals(history.getJSONObject(i).optString("key")))return Result.DUPLICATE;
            JSONArray updated=new JSONArray();
            for(int i=Math.max(0,history.length()-(HISTORY_LIMIT-1));i<history.length();++i)updated.put(history.getJSONObject(i));
            JSONObject item=new JSONObject();item.put("key",key);item.put("source",source);item.put("text",text);item.put("group",group);
            updated.put(item);
            return preferences.edit().putString("history",updated.toString()).commit()?Result.NEW:Result.FAILED;
        } catch (JSONException error) {return Result.FAILED;}
    }
    synchronized List<Item> history(){
        ArrayList<Item> items=new ArrayList<>();
        try {
            JSONArray saved=new JSONArray(preferences.getString("history","[]"));
            for(int i=0;i<saved.length();++i){JSONObject item=saved.getJSONObject(i);
                items.add(new Item(item.optString("key"),item.optString("source"),item.optString("text"),item.optBoolean("group")));}
        } catch (JSONException ignored) {}
        return items;
    }
}
